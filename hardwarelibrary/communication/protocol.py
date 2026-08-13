"""Describing an instrument protocol, without performing it.

The idea is sans-I/O, the principle behind h11 and wsproto: a protocol is a pure
transformation over bytes and never performs the exchange. A Frame turns named
values into the bytes to write and the bytes read back into named values; it owns
no port and stores nothing of what happened. A driver keeps the port and calls the
primitives of CommunicationPort itself, so the same description serves a driver
speaking to hardware and a debug port standing in for it.

Consequences worth noticing while reading:

  - a description is immutable and shareable; the result of a command is a plain
    dict returned to the caller, so two instruments cannot overwrite each other;
  - a frame parses whatever it is handed, and says how many bytes to read only
    where nothing else could know: a fixed-size binary frame;
  - a constant is stated once and serves both directions -- written on the way
    out, required on the way in -- which is what lets a debug port tell one
    command from another, and a driver notice an acknowledgement that is not its
    own;
  - there is no request class and no reply class: a frame becomes one or the
    other by the slot of the Command it sits in, which is also the only place
    that knows enough to name what failed to match;
  - decoding failure raises, naming what did not match, instead of being recorded
    in an attribute nobody checks.

Both directions are described. A driver writes the request and reads the reply; a
debug port reads the request and writes the reply, out of the same objects.

Where the two directions are the same statement, they are written once; where they
are not, they are both written out. A binary frame is packed and unpacked from one
struct format, because pack and unpack are exactly each other's inverse -- asking
for a second format there is how the old description ended up with '<lllx' to read
a position and '<lllc' to write one, two formats for the same thirteen bytes, one
of which had quietly lost the terminator. Text has no such luck: a template cannot
be turned into a regular expression without guessing a pattern per format spec, and
a regular expression cannot be turned back into a line at all. So a text frame
states both, and nothing anywhere is inferred -- the same refusal to guess that
makes the byte-order prefix mandatory.

This replaces the commands dict of communication/commands.py, which described the
protocol, built the bytes, performed the I/O, and then kept the reply on itself --
on a class attribute shared by every instance of a driver. SutterDevice is the
first driver to speak through it; see motion/sutterdevice.py.
"""

import json
import re
import string
from abc import ABC, abstractmethod
from struct import calcsize, error as StructError, pack, unpack
from typing import Callable, Iterator, Optional, Tuple, Type, Union



class ProtocolError(Exception):
    """Base for anything the description itself can refuse."""


class MissingArgument(ProtocolError):
    """A request needs a value the caller did not supply."""


class DidNotMatch(ProtocolError):
    """Bytes are not what the description says they should be."""


class ReplyDidNotMatch(DidNotMatch):
    """The bytes read back are not what this reply describes."""


class RequestDidNotMatch(DidNotMatch):
    """The bytes received are not what this request describes.

    Only a mock ever sees this, and usually not as an error: it is how one command
    in a dictionary declines a request that belongs to another.
    """


class BadDescription(ProtocolError):
    """A command description, usually read from a file, does not make sense."""


class Frame(ABC):
    """One half of a command: how to write it, and how to read it back.

    This is not "the command and its reply", it is the command and the
    reverse operation to read the command (and confirm proper formatting) so 
    we can create a DebugPort easily.

    Both halves are needed in both directions, which is the whole reason a
    description is worth having. A driver writes the request and reads the reply;
    a mock standing in for the instrument reads the request and writes the reply.
    Same objects, opposite roles -- the protocol is stated once and neither side
    owns it.

    readLength is what a reader must be told when nothing else could know it: a
    fixed-size binary frame has no terminator to stop at, so the number of bytes to
    ask for can come from nowhere but the description. A line needs no such answer,
    since the port already reads up to its own terminator.

    Three properties say what a frame carries, and they are easy to confuse:

      - fields is the raw list, in whichever shape the notation needs -- a
        converter per capture group for text, every packed name including the
        constants for binary;
      - arguments is the names a caller supplies, so the constants are gone;
      - parameters is those same names with their types, read off the converter
        for text and off the struct code for binary.

    parameters is built from arguments, so arguments is always the names half of
    parameters, and it is parameters alone that the contract below requires --
    arguments is a convenience the two concrete frames happen to offer. Neither is
    "arguments" in the ordinary Python sense: both are names, never values.

    A frame does not know whether it is a request or a reply, and there is no class
    for either. Which one it is depends only on the slot of the Command it sits in,
    and that is where the two are told apart -- a frame that failed to match says
    only that, and the Command says which half of which command was being read.
    """

    readLength = None

    @abstractmethod
    def encode(self, **values: object) -> bytes:
        """Build the bytes this frame puts on the wire.

        Args:
            **values: the values to write, passed by name, one per entry of
                parameters -- encode(power=0.5) for a frame that carries a power.
                Anything the description fixes is supplied by the description
                and must not be passed. The annotation is object because the
                type each value must have is not a property of this method but
                of the field it goes into, which only the description knows:
                parameters reports it, one name at a time.

        Returns:
            The bytes to write, terminator included, ready to hand to a port.
        """
        ...

    @abstractmethod
    def decode(self, data: Union[bytes, str]) -> dict:
        """Read bytes this frame describes and name what they carried.

        Args:
            data: the bytes read, or a str -- what a port hands over varies.

        Returns:
            A dict of {field name: value}, empty when the frame carries nothing
            but its own literal text or its own fixed bytes.

        Raises:
            DidNotMatch: when the bytes are not the ones this frame describes.
        """
        ...

    def faults(self) -> list:
        """Everything wrong with this frame that can be seen without using it.

        Only what the notation alone can settle: whether the two statements of a
        text line agree on how many values there are and what they are called,
        whether a struct format packs as many values as it names. Whether they
        agree about the line *itself* takes a round trip, which needs values and
        so belongs to the dictionary, not here.

        Returns:
            One sentence per fault, empty when there is nothing to say. A frame
            of a notation with nothing to check inherits this and says nothing.
        """
        return []

    @property
    @abstractmethod
    def parameters(self) -> tuple:
        """The names to pass this frame, and the names it hands back, with types.

        The two are the same list, since a frame is written and read from one
        description: encode takes these names as keywords and decode returns them
        as keys. Not used to encode or decode anything, though -- it exists so
        that a dictionary can explain itself out of the description rather than
        out of a comment.

        Returns:
            A (name, type name) pair per value, in the order the frame lays them
            out, such as (("x", "int32"), ("y", "int32"), ("z", "int32")). Empty
            when the frame is nothing but fixed text or fixed bytes.
        """
        ...


class TextFrame(Frame):
    """A line of ASCII, stated as the template that writes it and the expression
    that reads it.

    The template uses named fields, so a caller writes setPower(power=0.5) and
    never counts positional arguments: "p {power:0.3f}\r". Whatever ends the line is
    written into it, where it can be seen, rather than passed alongside: a
    terminator is simply more literal text, and instruments disagree about it enough
    -- \r, \n, \r\n, or nothing at all for the Integra -- that no default would
    serve.

    fields maps a name to the converter for its capture group, in group order:
    {"power": float} turns r"(\\d+\\.\\d+)" into {"power": 0.123}. A line with no
    capture groups, such as an "OK" acknowledgement, decodes to an empty dict -- it
    either matched or it raised.

    Neither notation is worked out from the other. A template could be turned into
    an expression by guessing a pattern per format spec, and the guess would be
    right often enough to be trusted and wrong quietly: a field with no spec would
    come back as text and nothing would say so. An expression cannot be turned back
    into a line at all. This module already refuses to let struct guess a byte
    order; guessing here is not of a different kind.

    One class serves both halves of a command. The template is what a driver sends
    when the frame is a request and what a mock answers when it is a reply; the
    expression is read by whichever of the two is listening.
    """

    def __init__(self, template: str, regex: str,
                 fields: Optional[dict] = None):
        """Describe a line by its two notations.

        The three arguments describe one line three ways, and they have to agree:
        "p {power:0.3f}\r" is written with r"p ([0-9.]+)\r" and {"power": float}.
        One placeholder, one capture group, one converter, all called power.

        Args:
            template: the str.format template that writes the line, terminator
                included, with a {name} where each value goes
            regex: the expression that reads the line back, with one capture
                group per value, in the same order the template writes them
            fields: the converter to run on each capture group, keyed by the
                name the template uses -- float for a power, int for a count.
                None or empty for a line with no values at all, such as an "OK".
        """
        self.template = template
        self.regex = regex
        self.fields = dict(fields or {})

    @property
    def arguments(self) -> tuple:
        """The names a caller must supply.

        They are the {name} placeholders of the template, and they are found by
        handing the template to string.Formatter().parse, which splits it into
        literal text and field names so that nothing has to be scanned by hand.

        Returns:
            Every placeholder name, in the order the template lays them out:
            ("power",) for "p {power:0.3f}\r", and ("register", "value") for
            "s r{register} {value}\r". Empty for a template of literal text
            only, such as "pa?\r", which is a request that takes no arguments.
        """
        return tuple(name for _, name, _, _ in string.Formatter().parse(self.template)
                     if name)

    @property
    def parameters(self) -> tuple:
        """Those same names, each with the type it is read back as.

        The names come from the template and the types from the converters, which
        are two independent lists: a name the converters do not mention is
        reported as text, since nothing says otherwise.

        Returns:
            A (name, type name) pair per placeholder, in template order:
            (("power", "float"),) for "p {power:0.3f}\r" described with
            {"power": float}.
        """
        return tuple((name, self.typeNameOf(self.fields[name])
                      if name in self.fields else "text")
                     for name in self.arguments)

    def faults(self) -> list:
        """What the template and the expression can be seen to disagree about.

        They are written out separately, so nothing but a check like this holds
        them together. Two disagreements show without sending anything: how many
        values there are, and what they are called.

        Returns:
            One sentence per fault, empty when the two notations line up.
        """
        try:
            expression = re.compile(self.regex)
        except re.error as error:
            return ["{0!r} is not a regular expression: {1}".format(self.regex, error)]

        if expression.groups != len(self.fields):
            return ["{0!r} captures {1} value(s) but {2} field(s) are named: {3}".format(
                self.regex, expression.groups, len(self.fields),
                ", ".join(self.fields) or "none")]

        written, read = set(self.arguments), set(self.fields)
        if written != read:
            return ["the template writes {0} and the fields name {1}".format(
                ", ".join(sorted(written)) or "nothing",
                ", ".join(sorted(read)) or "nothing")]
        return []

    @staticmethod
    def typeNameOf(converter: Callable[[str], object]) -> str:
        """Name a converter for the benefit of someone reading a usage line.

        A converter is often a type, and then its own name is the answer. When it is
        a function, what a reader wants is what it returns, which its annotation
        already says -- so a "0" or "1" field is announced as a bool rather than by
        the name of the function that makes one.

        This is a guess, and it is allowed to be one because nothing it returns
        ever reaches the wire: parameters is its only caller and usage() is the
        only thing that reads parameters. The rule that nothing here is inferred
        governs the protocol, not the sentence that explains it. Its worst answer
        is an ugly one -- "<lambda>" -- never a wrong frame.

        Args:
            converter: anything callable on a captured string -- a type such as
                float, or a function such as booleanFromZeroOrOne

        Returns:
            The name of what the converter returns when it is annotated, its own
            name otherwise, and its repr as a last resort for a lambda.
        """
        returned = getattr(converter, "__annotations__", {}).get("return")
        if returned is not None:
            return getattr(returned, "__name__", str(returned))
        return getattr(converter, "__name__", None) or str(converter)

    def encode(self, **values: object) -> bytes:
        """Write the line, substituting the values into the template.

        Args:
            **values: the values to substitute, passed by name, one per
                {name} in the template. A value the template never mentions is
                ignored, as str.format ignores it. Any object will do, since
                a format spec is applied to whatever it is handed -- a float for
                "{power:0.3f}", but equally a datetime for "{when:%H:%M}".

        Returns:
            The line as UTF-8 bytes, terminator included since the template
            carries it.

        Raises:
            MissingArgument: when a {name} of the template was not supplied,
                naming the field and listing what was given, rather than letting
                a bare KeyError out of str.format.
        """
        try:
            return self.template.format(**values).encode("utf-8")
        except KeyError as error:
            raise MissingArgument("{0} needs {1}, got {2}".format(
                self.template, error, sorted(values))) from None

    def decode(self, data: Union[bytes, str]) -> dict:
        """Read the line back and convert each captured group.

        Args:
            data: the line as read, bytes or str -- what a port hands over
                varies. Anything around the match is ignored, since re.search is
                used: where a line ends is the port's business.

        Returns:
            A dict of {field name: converted value}, empty when the expression
            has no capture groups.

        Raises:
            DidNotMatch: when the expression does not match, quoting both sides.
            ProtocolError: when the expression and the fields disagree on how
                many values the line carries.
        """
        text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        match = re.search(self.regex, text)
        if match is None:
            raise DidNotMatch("expected {0!r}, got {1!r}".format(self.regex, text))

        groups = match.groups()
        if len(groups) != len(self.fields):
            raise ProtocolError(
                "{0!r} captured {1} group(s) but {2} field(s) were named".format(
                    self.regex, len(groups), len(self.fields)))
        return {name: converter(value)
                for (name, converter), value in zip(self.fields.items(), groups)}


class BinaryFrame(Frame):
    """A fixed-size binary frame, named field by field, readable and writable.

    fields names each value in the struct format, in order; constants are the ones
    nobody supplies, such as a header byte or a trailing carriage return. A
    constant is written on the way out and required on the way in, so the one line
    that produces b"M" also refuses a frame that does not begin with it -- which is
    how a mock tells one command from another, and how a driver is told that an
    acknowledgement was not the one it expected.

    Padding ('x') has no place here. It can be unpacked but not packed, so a frame
    that skipped its terminator could be read and never written, and the mock
    direction would need a second format for the same bytes. Name the byte and make
    it a constant instead.
    """

    byteOrderPrefixes = ("<", ">", "!", "=")

    # What each struct code is called when a command explains itself. A class
    # attribute rather than a module one, so a frame for an instrument that reads
    # its own kind of value can add to it, the way CommandDictionary does with
    # converters.
    typeNames = {
        "c": "byte", "?": "bool", "b": "int8", "B": "uint8",
        "h": "int16", "H": "uint16", "i": "int32", "I": "uint32",
        "l": "int32", "L": "uint32", "q": "int64", "Q": "uint64",
        "e": "float16", "f": "float", "d": "double", "s": "bytes", "p": "bytes",
    }

    def __init__(self, struct: str, fields: tuple = (),
                 constants: Optional[dict] = None):
        """Describe a frame as a struct format, one name per packed value.

        Args:
            struct: a struct format, byte order included, or the frame it builds
                is the one a C compiler would want rather than the one the
                instrument expects
            fields: one name per value the format packs, in order, padding
                excluded since padding packs no value
            constants: the values nobody supplies, keyed by field name -- a
                header byte, a terminator, a fixed acknowledgement. Written on
                the way out, required on the way in.

        Raises:
            ProtocolError: when the format states no byte order.
            BadDescription: when constants fixes a name fields does not list,
                which would otherwise fail much later and much less clearly.
        """
        self.requireExplicitByteOrder(struct)
        self.struct = struct
        self.fields = tuple(fields)
        self.constants = dict(constants or {})

        unknown = sorted(set(self.constants) - set(self.fields))
        if unknown:
            raise BadDescription("{0} fixes {1}, which {2} does not name".format(
                self.struct, ", ".join(unknown), list(self.fields)))

    @property
    def readLength(self) -> int:
        """How many bytes to read before this frame can be decoded.

        Returns:
            The size of the format, so it never has to be kept in step by hand.
            This is the one thing a caller could not work out for itself: a
            fixed-size frame has no terminator to stop at.
        """
        return calcsize(self.struct)

    @property
    def arguments(self) -> tuple:
        """The names a caller must supply.

        Returns:
            A tuple of every field that is not a constant, in format order. A
            frame made only of constants returns an empty tuple.
        """
        return tuple(name for name in self.fields if name not in self.constants)

    @property
    def parameters(self) -> tuple:
        """Each non-constant field with the type its format packs it as.

        Returns:
            A tuple of (name, type name) pairs, in format order, the type being
            read off the struct code -- "l" is reported as int32. A code this
            class does not name is reported as "unknown" rather than hidden.
        """
        codeOf = dict(zip(self.fields, self.structCodes(self.struct)))
        return tuple((name, self.typeNames.get(codeOf.get(name), "unknown"))
                     for name in self.arguments)

    def faults(self) -> list:
        """Whether the format and the field names agree on how many values there are.

        Caught here rather than at the first decode, where it surfaces today as a
        ProtocolError in the middle of an exchange.

        Returns:
            One sentence per fault, empty when the counts line up.
        """
        codes = self.structCodes(self.struct)
        if len(codes) != len(self.fields):
            return ["{0} packs {1} value(s) but {2} field(s) are named: {3}".format(
                self.struct, len(codes), len(self.fields),
                ", ".join(self.fields) or "none")]
        return []

    @classmethod
    def requireExplicitByteOrder(cls, struct: str) -> None:
        """Refuse a struct format that does not begin with a byte-order prefix.

        Without one, struct uses native sizes and native alignment: "clllc" is 33
        bytes on this machine rather than the 14 the instrument expects, an "l" is
        whatever a C long happens to be, and padding appears between the fields.
        The frame is then correct for the compiler and wrong for the wire, and
        nothing downstream would notice -- the same failure the ctypes variant
        needed _pack_ = 1 to avoid, at the price of one character here.

        A classmethod, and the prefixes a class attribute, so that a frame for a
        machine whose formats are spelled differently overrides the pair rather
        than working around a module function it cannot reach.

        Args:
            struct: a struct format, expected to start with one of the prefixes
                byteOrderPrefixes lists

        Returns:
            Nothing. It is a guard, called for its refusal.

        Raises:
            ProtocolError: when the prefix is missing, giving both the length the
                format would really produce and the one that was meant, and the
                corrected format to write instead.
        """
        if not struct.startswith(cls.byteOrderPrefixes):
            raise ProtocolError(
                "{0!r} has no byte-order prefix, so struct would use native sizes "
                "and alignment: {1} bytes instead of {2}. Write {3!r}.".format(
                    struct, calcsize(struct), calcsize("<" + struct), "<" + struct))

    @staticmethod
    def structCodes(struct: str) -> tuple:
        """Split a struct format into the type code of each value it packs.

        Args:
            struct: a struct format, byte-order prefix included -- the prefix is
                skipped, not treated as a code

        Unlike typeNameOf, which also serves nothing but the usage text, this is
        not a guess: the struct codes are a closed, documented set, so it can be
        read exactly and is expected to be.

        Returns:
            One code per packed value, repeat counts expanded, so that the codes
            line up with the field names one for one. Padding yields no value and
            so no code, and whitespace is skipped as struct itself skips it. A
            count on "s" means one string that long, not that many strings, which
            is the one place the rule is not repetition.
        """
        codes = []
        count = ""
        for character in struct[1:]:
            if character.isspace():
                continue
            if character.isdigit():
                count += character
                continue
            repeats = int(count) if count else 1
            count = ""
            if character == "x":
                continue
            codes.extend([character] if character in "sp" else [character] * repeats)
        return tuple(codes)

    def encode(self, **arguments: object) -> bytes:
        """Pack the frame, constants and arguments interleaved in field order.

        Args:
            **arguments: the values to pack, passed by name, one per entry of
                arguments. A constant must not be passed: the description
                supplies it. What each value must be is decided by its struct
                code and by nothing here -- an int for "l", bytes for "c" -- so
                it is parameters that answers, and a wrong kind is refused by
                pack rather than by the signature.

        Returns:
            The packed frame, exactly readLength bytes long.

        Raises:
            MissingArgument: for a field nobody supplied, naming it and listing
                what was given.
            ProtocolError: for a value struct cannot pack into its format, such
                as a string where a long was expected.
        """
        values = []
        for name in self.fields:
            if name in self.constants:
                values.append(self.constants[name])
            elif name in arguments:
                values.append(arguments[name])
            else:
                raise MissingArgument("{0} needs {1}, got {2}".format(
                    self.struct, name, sorted(arguments)))
        try:
            return pack(self.struct, *values)
        except StructError as error:
            raise ProtocolError("cannot pack {0} into {1}: {2}".format(
                values, self.struct, error)) from None

    def decode(self, data: bytes) -> dict:
        """Unpack the frame and name what it carried, constants left out.

        A constant is checked rather than returned: it carries no information, and
        a frame whose header is wrong is not this frame at all.

        Args:
            data: exactly readLength bytes. Unlike a line, a frame cannot be
                surrounded by anything, since its length is its only boundary.

        Returns:
            A dict of {field name: value} for the non-constant fields only, so a
            frame made of constants alone decodes to an empty dict.

        Raises:
            DidNotMatch: when the length is wrong, or when a constant is not the
                value the description fixed -- which is how a mock tells one
                command from another.
            ProtocolError: when the format and the field names disagree on how
                many values the frame carries.
        """
        if len(data) != self.readLength:
            raise DidNotMatch("expected {0} bytes for {1}, got {2}".format(
                self.readLength, self.struct, len(data)))
        values = unpack(self.struct, bytes(data))
        if len(values) != len(self.fields):
            raise ProtocolError(
                "{0} unpacks {1} value(s) but {2} field(s) were named".format(
                    self.struct, len(values), len(self.fields)))

        named = dict(zip(self.fields, values))
        for name, constant in self.constants.items():
            if named[name] != constant:
                raise DidNotMatch("{0} expects {1}={2!r}, got {3!r}".format(
                    self.struct, name, constant, named[name]))
        return {name: value for name, value in named.items()
                if name not in self.constants}


class Command:
    """One request and the reply it expects, named for a driver to call by name.

    A command is a description and nothing else: it says what to send and what
    should come back, and carries neither the data nor the transmission. encode()
    hands the caller the bytes to write, decode() turns what came back into
    values, and the port in between is the caller's.

    The same description read from the other end plays the instrument:
    decodeRequest() is what a mock hears, encodeReply() what it answers. Two pairs
    of methods, one protocol, no second table to keep in step -- where the Command
    this replaces needed a request decoder and a reply encoder written out beside
    the request encoder and the reply decoder.

    That is the whole difference from the Command this replaces, which described
    the protocol, built the bytes, performed the exchange, and then kept the
    reply on itself.

    A command is also where the two halves are told apart. A Frame is neither a
    request nor a reply -- it becomes one by being put in one of these two slots --
    so a frame that fails to match says only that, and a command turns it into a
    RequestDidNotMatch or a ReplyDidNotMatch naming itself. Which is more than
    either one could say on its own: a frame does not know what command it
    belongs to.
    """

    def __init__(self, name: str, request: Frame, reply: Optional[Frame] = None,
                 sets: Optional[dict] = None, specimen: Optional[dict] = None):
        """Pair a request with the reply it expects, under the name a driver uses.

        Args:
            name: how a driver asks for this command, and how it names itself in
                an error
            request: the frame the driver writes and a mock reads
            reply: the frame the driver reads and a mock writes, or None for a
                command the instrument does not answer
            sets: what receiving this command does to the instrument's state,
                as {field name: value}, for what the request does not carry.
                HOME takes no arguments and yet moves the stage to the origin,
                and nothing about the bytes on the wire could say so. This is the
                one thing here that describes the instrument rather than the
                protocol, and it exists so that a debug port needs no code of its
                own; a driver never reads it.
            specimen: a value per field for validate() to send through this
                command and expect back, when the ones it makes from the declared
                types will not do -- an expression that refuses a zero, say.
                Like sets, it is not part of the protocol, and only validate()
                reads it.
        """
        self.name = name
        self.request = request
        self.reply = reply
        self.sets = dict(sets or {})
        self.specimen = dict(specimen or {})

    @property
    def expectsReply(self) -> bool:
        """Whether the instrument answers this command at all.

        Returns:
            True when a reply was described, so a caller knows whether to read.
        """
        return self.reply is not None

    def encode(self, **arguments: object) -> bytes:
        """Build the bytes to send -- the driver's half of the exchange.

        Args:
            **arguments: the values the request carries, passed by name --
                one per entry of request.parameters.

        Returns:
            The bytes to write. What happens to them is the caller's business:
            nothing here touches a port.
        """
        return self.request.encode(**arguments)

    def decode(self, data: Union[bytes, str]) -> dict:
        """Read what the instrument answered -- the driver's other half.

        Args:
            data: the bytes read back. How many to read is reply.readLength when
                the reply is binary, and the port's own terminator when it is a
                line.

        Returns:
            A dict of {field name: value}, returned to the caller and stored
            nowhere, so two callers of one description cannot overwrite each
            other.

        Raises:
            ProtocolError: when this command expects no reply, since decoding one
                means the caller read something it should not have.
            ReplyDidNotMatch: when the instrument answered something else, naming
                this command.
        """
        if self.reply is None:
            raise ProtocolError("{0} expects no reply".format(self.name))
        return self.decodeHalf(self.reply, data, ReplyDidNotMatch)

    def decodeRequest(self, data: Union[bytes, str]) -> dict:
        """Read a request addressed to us -- the mock's half of encode.

        Args:
            data: one complete request as received.

        Returns:
            A dict of the arguments it carried, empty for a command that takes
            none.

        Raises:
            RequestDidNotMatch: when the bytes are some other command's request,
                which is how a mock picks the right one out of a dictionary
                rather than an error a driver would ever see.
        """
        return self.decodeHalf(self.request, data, RequestDidNotMatch)

    def decodeHalf(self, half: Frame, data: Union[bytes, str],
                   mismatch: Type[DidNotMatch]) -> dict:
        """Decode one half, saying which half of which command failed to match.

        A frame knows only that the bytes are not the ones it describes. Naming the
        command, and which end of it was being read, is something only a command can
        do -- so it is done here rather than passed down.

        Args:
            half: the frame to decode with, this command's request or its reply
            data: the bytes to read
            mismatch: the exception class to raise on failure, which is what
                records the role -- RequestDidNotMatch or ReplyDidNotMatch

        Returns:
            Whatever the frame decoded, untouched.

        Raises:
            The mismatch given, with this command's name prefixed to the frame's
            own account of what did not match.
        """
        try:
            return half.decode(data)
        except DidNotMatch as error:
            raise mismatch("{0}: {1}".format(self.name, error)) from None

    def encodeReply(self, **values: object) -> bytes:
        """Build the answer the instrument would give -- the mock's half of decode.

        Args:
            **values: the values the reply carries, passed by name -- one per
                entry of reply.parameters.

        Returns:
            The bytes a mock writes back, terminator included.

        Raises:
            ProtocolError: when this command expects no reply, since a mock that
                answered would be answering a command the instrument leaves
                silent.
        """
        if self.reply is None:
            raise ProtocolError("{0} expects no reply".format(self.name))
        return self.reply.encode(**values)


def booleanFromZeroOrOne(text: str) -> bool:
    """Read a "0" or "1" field as a boolean.

    Args:
        text: one capture group, expected to be "0" or "1"

    Returns:
        True for "1", False for anything else -- an instrument that answers
        neither is refused by the expression, not here.
    """
    return text == "1"


def integerFromHexadecimal(text: str) -> int:
    """Read a field written in hexadecimal as an integer.

    Args:
        text: one capture group of hexadecimal digits, with or without a 0x
            prefix, which int accepts either way

    Returns:
        The value the digits spell.

    Raises:
        ValueError: when the group is not hexadecimal, which means the
            expression captured something it should not have.
    """
    return int(text, 16)


class CommandDictionary:
    """Every command one device understands, by name, read from a file.

    A driver's protocol is a table, and a table is data: a description read from
    JSON builds the same objects a driver would write by hand, so a protocol can
    be read, reviewed and corrected without touching the code that speaks it.

    JSON rather than TOML or YAML because it is in the standard library of every
    Python the package supports; tomllib arrives only in 3.11, and YAML would be a
    dependency for a file nobody edits at runtime.

    A command is described by a request and, when there is one, a reply. Which key
    is present says which kind it is, so nothing declares a type twice, and the key
    names the notation its string is written in: a str.format template on the way
    out, a regular expression on the way in, a struct format for bytes in either
    direction.

        "SET_POWER": {
          "request": {"template": "p {power:0.3f}\r",
                      "regex": "p ([0-9.]+)\r",
                      "fields": {"power": "float"}},
          "reply":   {"regex": "OK", "template": "OK\r\n"}
        },
        "GET_POWER": {
          "request": {"template": "pa?\r", "regex": "pa\\?\r"},
          "reply":   {"regex": "(\\d+\\.\\d+)", "template": "{power:0.4f}\r\n",
                      "fields": {"power": "float"}}
        },
        "MOVE": {
          "request": {"struct": "<clllc",
                      "fields": ["header", "x", "y", "z", "terminator"],
                      "constants": {"header": "M", "terminator": "\r"}},
          "reply":   {"struct": "<c", "fields": ["acknowledgement"],
                      "constants": {"acknowledgement": "\r"}}
        }

    A text frame states both of its notations and a binary one states a single
    format, because
    a struct already reads both ways and a template and a regex do not. Both are
    required: a request nobody can read and a reply nobody can write are half
    descriptions, and the mock they are meant to serve would only find that out at
    the moment it failed.

    Either frame may carry values and either may carry none, in any
    combination. SET_POWER above takes an argument and is answered by a bare
    acknowledgement; GET_POWER takes none and is answered by a value; MOVE takes
    three and is answered by a fixed byte. What a frame carries is written in
    fields, and what fields means follows the notation:

      - on a text frame, one entry per capture group of the regex, in group
        order,
        naming the converter to run on it. Those names are also the {names} of
        the template, since a value written and the same value read back are not
        two different things;
      - on a binary frame, one name per value the struct packs, in order, and
        constants picks out the ones nobody supplies -- a header byte, a
        terminator, a fixed acknowledgement.

    Nothing checks that a template and its regex agree about what they carry; only
    sending a command and reading it back does, which is why every command in the
    tests below is put through that round trip.

    Reads like a dict. The methods that turn a description into objects are here
    rather than beside it, so a device whose protocol needs something this does
    not cover subclasses and overrides one of them -- adding a converter, or a
    third kind of request -- instead of the module growing another function.
    """

    # The one thing a file cannot carry is a callable, so a text field names its
    # converter and the name is looked up here. Deliberately short: a protocol
    # file describes a protocol, and anything wanting real code belongs in the
    # driver. A subclass may add to it.
    converters = {
        "float": float,
        "integer": int,
        "text": str,
        "boolean01": booleanFromZeroOrOne,
        "hexInteger": integerFromHexadecimal,
    }

    def __init__(self, commands: dict, deviceName: Optional[str] = None):
        """Hold already-built commands by name. Use fromFile to read a description.

        Args:
            commands: {name: Command}, copied so that the dictionary cannot be
                changed behind its back
            deviceName: the instrument's name, carried only so that an error can
                say whose protocol was being read
        """
        self.commands = dict(commands)
        self.deviceName = deviceName

    @classmethod
    def fromFile(cls, path: str) -> "CommandDictionary":
        """Read one device's commands from a JSON file.

        Args:
            path: the file to read

        Returns:
            A dictionary of the commands it describes.

        Raises:
            OSError: when the file cannot be read.
            json.JSONDecodeError: when it is not JSON.
            BadDescription: when it is JSON but not a protocol.
        """
        with open(path, "r") as file:
            return cls.fromDescription(json.load(file))

    @classmethod
    def fromJSON(cls, text: str) -> "CommandDictionary":
        """Read them from JSON already in hand.

        Args:
            text: the description as JSON, from wherever it came

        Returns:
            A dictionary of the commands it describes.
        """
        return cls.fromDescription(json.loads(text))

    @classmethod
    def fromDescription(cls, description: dict) -> "CommandDictionary":
        """Build from the description itself, however it was obtained.

        Args:
            description: {"device": name, "commands": {name: {...}}}. The device
                name is optional; the commands are not.

        Returns:
            A dictionary whose command order is the description's order, since
            that is usually the order whoever wrote the file thought in.

        Raises:
            BadDescription: when there are no commands at all, or when any one of
                them does not make sense.
        """
        if "commands" not in description:
            raise BadDescription("no commands: expected {'device': ..., 'commands': {...}}")
        return cls({name: cls.commandFrom(name, one)
                    for name, one in description["commands"].items()},
                   deviceName=description.get("device"))

    @classmethod
    def commandFrom(cls, name: str, description: dict) -> Command:
        """Build one named command from its description.

        Args:
            name: the command's name, used both for the Command and to say which
                command an error is about
            description: {"request": {...}} and, when the instrument answers,
                {"reply": {...}}, plus an optional {"sets": {...}} for a state
                change the request does not carry

        Returns:
            The command, its reply None when none was described.

        Raises:
            BadDescription: when there is no request, or when either half does
                not make sense.
        """
        where = "command {0!r}".format(name)
        if "request" not in description:
            raise BadDescription("{0}: no request".format(where))
        reply = description.get("reply")
        return Command(name, cls.requestFrom(description["request"], where),
                       cls.replyFrom(reply, where) if reply is not None else None,
                       sets=description.get("sets"),
                       specimen=description.get("specimen"))

    @classmethod
    def requestFrom(cls, description: dict, where: str) -> Frame:
        """Build the request half: a template for text, a struct for binary.

        Args:
            description: the "request" object. Which key is present says which
                notation it is written in.
            where: how to name this command in an error

        Returns:
            A TextFrame or a BinaryFrame, according to the key found.

        Raises:
            BadDescription: when neither notation is present, or when a text
                request states a template without the expression that reads it
                back.
            ProtocolError: when a struct format states no byte order.
        """
        if "template" in description:
            if "regex" not in description:
                raise BadDescription(
                    "{0}: a text request needs a regex as well as its template, "
                    "so that a mock can read what the driver writes".format(where))
            return TextFrame(description["template"], description["regex"],
                             fields=cls.convertersFor(description.get("fields", {}), where))
        if "struct" in description:
            return BinaryFrame(description["struct"],
                               fields=tuple(description.get("fields", ())),
                               constants=cls.constantsFrom(description))
        raise BadDescription(
            "{0}: a request needs a template, for text, or a struct, for binary".format(where))

    @classmethod
    def replyFrom(cls, description: dict, where: str) -> Frame:
        """Build the reply half: a regex for text, a struct for binary.

        A text reply states both notations, like a text request; a binary one needs
        only its struct, since pack and unpack are already each other's inverse.

        Args:
            description: the "reply" object
            where: how to name this command in an error

        Returns:
            A TextFrame or a BinaryFrame, according to the key found.

        Raises:
            BadDescription: when neither notation is present, or when a text
                reply states an expression without the template that writes it.
            ProtocolError: when a struct format states no byte order.
        """
        if "regex" in description:
            if "template" not in description:
                raise BadDescription(
                    "{0}: a text reply needs a template as well as its regex, "
                    "so that a mock can write what the driver reads".format(where))
            return TextFrame(description["template"], description["regex"],
                             fields=cls.convertersFor(description.get("fields", {}), where))
        if "struct" in description:
            return BinaryFrame(description["struct"],
                               fields=tuple(description.get("fields", ())),
                               constants=cls.constantsFrom(description))
        raise BadDescription(
            "{0}: a reply needs a regex, for text, or a struct, for binary".format(where))

    @classmethod
    def constantsFrom(cls, description: dict) -> dict:
        """Turn the constants of a binary frame from text in a file into bytes.

        Args:
            description: a "request" or "reply" object, whose "constants" is read
                if present

        Returns:
            {field name: bytes}, empty when the frame fixes nothing.
        """
        return {name: cls.bytesFrom(value)
                for name, value in description.get("constants", {}).items()}

    @classmethod
    def convertersFor(cls, fields: dict, where: str) -> dict:
        """Turn {"power": "float"} from a file into {"power": float}.

        Args:
            fields: {field name: converter name}, as a file writes it
            where: how to name this command in an error

        Returns:
            {field name: callable}, in the same order, ready for a TextFrame.

        Raises:
            BadDescription: when a converter name is not one this class knows,
                listing the ones that do exist.
        """
        resolved = {}
        for name, converterName in fields.items():
            if converterName not in cls.converters:
                raise BadDescription(
                    "{0}: {1} names the converter {2!r}, which is not one of {3}".format(
                        where, name, converterName, ", ".join(sorted(cls.converters))))
            resolved[name] = cls.converters[converterName]
        return resolved

    @staticmethod
    def bytesFrom(text: str) -> bytes:
        """Turn a constant written in a file into the byte it stands for.

        Args:
            text: one character of a JSON string, such as "M" or "\r"

        Returns:
            The bytes, encoded latin-1 so that \xfe stays one byte rather than
            becoming the two UTF-8 would spell it with.
        """
        return text.encode("latin-1")

    @property
    def names(self) -> tuple:
        """Every command this device understands.

        Returns:
            The names, in the order the description listed them.
        """
        return tuple(self.commands)

    def __getitem__(self, name: str) -> Command:
        """Look one command up by name.

        Args:
            name: the command's name, as the description spells it

        Returns:
            The command.

        Raises:
            KeyError: naming the device and listing the commands it does have,
                since a typo is the likeliest reason to be here.
        """
        if name not in self.commands:
            raise KeyError("{0} has no command {1!r}; it has {2}".format(
                self.deviceName or "this device", name, ", ".join(sorted(self.commands))))
        return self.commands[name]

    def recognize(self, data: Union[bytes, str]) -> Tuple[Command, dict]:
        """Work out which command a request belongs to, and what it carried.

        Every command is asked in turn whether the bytes are its request, and the
        first that says yes wins -- so a mock dispatches on the same descriptions
        the driver sends with, and no prefix table is written twice.

        Args:
            data: one complete request. Deciding where a request ends in a stream
                is the port's business, exactly as it is on the reply side.

        Returns:
            A (command, arguments) pair: the command that recognised the bytes,
            and the dict its request decoded to.

        Raises:
            RequestDidNotMatch: when no command recognises the bytes, naming the
                device and quoting them.
        """
        for command in self.commands.values():
            try:
                return command, command.decodeRequest(data)
            except DidNotMatch:
                continue
        raise RequestDidNotMatch("{0} has no command matching {1!r}".format(
            self.deviceName or "this device", data))

    # A value of each type, for validate() to send through a description and get
    # back. Deliberately dull: a specimen is not test data, it only has to survive
    # the trip. 1 rather than 0, and "1" rather than "", because an expression that
    # excludes a leading zero or an empty group is common and would refuse those.
    # A subclass may add to it; one command may override it with "specimen".
    specimens = {
        "float": 0.5, "double": 0.5, "float16": 0.5,
        "int": 1, "int8": 1, "uint8": 1, "int16": 1, "uint16": 1,
        "int32": 1, "uint32": 1, "int64": 1, "uint64": 1,
        "bool": True,
        "str": "1", "text": "1",
        "byte": b"1",
    }

    def validate(self) -> "CommandDictionary":
        """Refuse a description that is wrong about itself.

        Reading a file only catches what is missing or misspelled. What it cannot
        catch is a description that parses and then does not work: a template and
        an expression that describe different lines, a struct that packs a
        different number of values than it names, a command whose request another
        command answers to first. None of those show until something speaks the
        protocol -- usually a debug port, months later.

        So this speaks it. Every command is written out with specimen values and
        read straight back, and every request is handed to recognize() to check it
        is taken for itself. Call it in a driver's test, once, over the protocol
        that driver ships.

        Returns:
            The dictionary, so a description can be read and checked in one
            breath: CommandDictionary.fromFile(path).validate().

        Raises:
            BadDescription: listing every fault at once, since a file with three
                mistakes should not be corrected three times.
        """
        found = self.faults()
        if found:
            raise BadDescription("{0} is not consistent with itself:\n  {1}".format(
                self.deviceName or "this device", "\n  ".join(found)))
        return self

    def faults(self) -> list:
        """Everything wrong with this description, without raising.

        Returns:
            One sentence per fault, each naming the command and the half it is
            about. Empty for a description that is right about itself.
        """
        found = []
        for name, command in self.commands.items():
            ofRequest = self.faultsOfHalf(name, "request", command.request,
                                          command.specimen)
            found.extend(ofRequest)
            if command.reply is not None:
                found.extend(self.faultsOfHalf(name, "reply", command.reply,
                                               command.specimen))
            if not ofRequest:
                found.extend(self.faultsOfRecognition(name, command))
        return found

    def faultsOfHalf(self, name: str, role: str, frame: Frame, specimen: dict) -> list:
        """Everything wrong with one half of one command.

        A frame that does not add up is not then written out: the round trip
        would fail for the reason already given, and one mistake deserves one
        sentence.

        Args:
            name: the command's name
            role: "request" or "reply", to say which half
            frame: the frame to check
            specimen: values this command states for itself

        Returns:
            One sentence per fault, each prefixed with the command and the half.
        """
        where = "{0} {1}".format(name, role)
        found = ["{0}: {1}".format(where, fault) for fault in frame.faults()]
        if found:
            return found
        return self.faultsOfRoundTrip(where, frame, specimen)

    def faultsOfRoundTrip(self, where: str, frame: Frame, specimen: dict) -> list:
        """Write a frame out with specimen values and read them straight back.

        This is the only check that can catch two notations describing different
        lines, because it is the only one that makes a line.

        Args:
            where: the command and half being checked, for the message
            frame: the frame to write and read
            specimen: values this command gives for itself, overriding the ones
                made from the declared types

        Returns:
            One sentence per fault, empty when what went out came back.
        """
        values, missing = self.specimenFor(frame, specimen)
        if missing is not None:
            return ["{0}: {1}".format(where, missing)]
        try:
            readBack = frame.decode(frame.encode(**values))
        except Exception as error:
            return ["{0}: {1} cannot be written and read back: {2}".format(
                where, values, error)]
        if readBack != values:
            return ["{0}: wrote {1} and read back {2}".format(where, values, readBack)]
        return []

    def faultsOfRecognition(self, name: str, command: Command) -> list:
        """Check that a command's own request is taken for that command.

        Two commands can describe requests that each other's descriptions accept
        -- a text one whose expression is loose enough to match another's line, or
        a binary one that forgot to fix its header. recognize() then hands a debug
        port the wrong command, and the driver is answered as though it had asked
        something else.

        Args:
            name: the command's name
            command: the command itself

        Only reached when the request is sound on its own, since a request that
        cannot be written and read back has already been reported and would fail
        this too, for the same reason.

        Returns:
            One sentence per fault, empty when the command recognises itself.
            Silent when no specimen could be made, since the round trip has
            already said so.
        """
        values, missing = self.specimenFor(command.request, command.specimen)
        if missing is not None:
            return []
        try:
            recognized, _ = self.recognize(command.request.encode(**values))
        except Exception as error:
            return ["{0}: no command recognises its own request: {1}".format(name, error)]
        if recognized.name != name:
            return ["{0}: its request is taken for {1}, which is described first".format(
                name, recognized.name)]
        return []

    def specimenFor(self, frame: Frame, given: dict) -> Tuple[Optional[dict], Optional[str]]:
        """A value for each name a frame carries, to send through it and back.

        Args:
            frame: the frame to make values for
            given: what the command states for itself, which wins over the types

        Returns:
            A (values, complaint) pair, exactly one of which is None: the values
            to use, or the reason there are none -- a type this class has no
            specimen for, which the description must then supply itself.
        """
        values = {}
        for name, typeName in frame.parameters:
            if name in given:
                values[name] = given[name]
            elif typeName in self.specimens:
                values[name] = self.specimens[typeName]
            else:
                return None, ('no specimen for {0}, of type {1}; state one with '
                              '"specimen"'.format(name, typeName))
        return values, None

    def usage(self) -> str:
        """Returns every command, what to pass it and what it answers, as text.

        This is what someone needs before writing a single call: the names to give
        and the names that come back. It is read off the description, so unlike a
        comment or a README it cannot say something the protocol no longer does.

        Commands appear in the order the description listed them, since that order
        is usually the one whoever wrote the file thought in.

        Returns:
            The whole text, one paragraph per command, ready to print.
        """
        lines = ["{0}: {1} commands".format(self.deviceName or "This device", len(self))]
        for name in self.names:
            lines.extend(self.usageFor(self.commands[name]))
        return "\n".join(lines)

    def usageFor(self, command: Command) -> list:
        """Explain one command: how to call it, and what comes back.

        Args:
            command: the command to describe

        Returns:
            Its lines, starting with a blank one so that paragraphs separate when
            they are joined. A command is shown as a call with its arguments,
            then one line for the answer: the values it carries, or that it
            carries none, or that the instrument does not answer at all.
        """
        lines = ["", "  {0}({1})".format(command.name, self.listed(command.request))]
        if not command.expectsReply:
            lines.append("      the instrument does not answer")
        elif not command.reply.parameters:
            lines.append("      answers, carrying no values")
        else:
            lines.append("      answers {0}".format(self.listed(command.reply)))
        return lines

    @staticmethod
    def listed(frame: Frame) -> str:
        """Set out one frame's values for a usage line.

        Args:
            frame: a command's request or its reply

        Returns:
            "name: type, name: type" in the order the frame carries them, and
            an empty string for a frame that carries none -- which is what makes an
            argumentless command print as NAME().
        """
        return ", ".join("{0}: {1}".format(name, typeName)
                         for name, typeName in frame.parameters)

    def __str__(self) -> str:
        """Explain the whole protocol, so that printing a dictionary is enough.

        Returns:
            What usage() returns.
        """
        return self.usage()

    def __contains__(self, name: str) -> bool:
        """Whether the device understands a command of that name.

        Args:
            name: a command name to look for

        Returns:
            True when it is one of this device's commands.
        """
        return name in self.commands

    def __iter__(self) -> Iterator[str]:
        """Iterate over the command names, as a dict does.

        Returns:
            An iterator over the names, in description order.
        """
        return iter(self.commands)

    def __len__(self) -> int:
        """How many commands the device understands.

        Returns:
            The count, which is also what usage() announces.
        """
        return len(self.commands)
