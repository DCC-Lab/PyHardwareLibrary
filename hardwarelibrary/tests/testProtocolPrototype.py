"""A prototype protocol description, developed in isolation inside its test file.

Nothing here is imported by the library, and nothing here touches a port: this is
a sketch of how an instrument protocol could be *described*, so the design can be
judged before any driver depends on it.

The idea is sans-I/O, the principle behind h11 and wsproto: the protocol is a pure
transformation over bytes and never performs the exchange. A Frame turns named
values into the bytes to write and the bytes read back into named values; it owns
no port and stores nothing of what happened. That is what separates this from the
Command it would replace, which describes the protocol, builds the bytes, performs
the I/O, and then keeps the reply on itself -- on a class attribute shared by every
instance of a driver.

Consequences worth noticing while reading:

  - a description is immutable and shareable; the result of a command is a plain
    dict returned to the caller, so two instruments cannot overwrite each other;
  - a frame parses whatever it is handed, and says how many bytes to read only
    where nothing else could know: a fixed-size binary frame;
  - there is no request class and no reply class: a frame becomes one or the
    other by the slot of the Command it sits in, which is also the only place
    that knows enough to name what failed to match;
  - a constant is stated once and serves both directions -- written on the way
    out, required on the way in -- which is what lets a mock tell one command
    from another, and a driver notice an acknowledgement that is not its own;
  - decoding failure raises, naming what did not match, instead of being recorded
    in an attribute nobody checks.

Both directions are built here. A driver writes the request and reads the reply; a
mock standing in for the instrument reads the request and writes the reply, out of
the same objects.

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
"""

import env
import json
import os
import re
import string
import tempfile
import unittest
from abc import ABC, abstractmethod
from struct import calcsize, error as StructError, pack, unpack
from typing import Callable, Iterator, Optional, Tuple, Type, Union


# ---------------------------------------------------------------------------
# The prototype
# ---------------------------------------------------------------------------

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

        Returns:
            One code per packed value, repeat counts expanded, so that the codes
            line up with the field names one for one. Padding yields no value and
            so no code. A count on "s" means one string that long, not that many
            strings, which is the one place the rule is not repetition.
        """
        codes = []
        count = ""
        for character in struct[1:]:
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

    def __init__(self, name: str, request: Frame, reply: Optional[Frame] = None):
        """Pair a request with the reply it expects, under the name a driver uses.

        Args:
            name: how a driver asks for this command, and how it names itself in
                an error
            request: the frame the driver writes and a mock reads
            reply: the frame the driver reads and a mock writes, or None for a
                command the instrument does not answer
        """
        self.name = name
        self.request = request
        self.reply = reply

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
                {"reply": {...}}

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
                       cls.replyFrom(reply, where) if reply is not None else None)

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTextFrameWritingALine(unittest.TestCase):
    def testBuildsAConstantRequest(self):
        self.assertEqual(TextFrame("pa?\r", r"pa\?\r").encode(), b"pa?\r")

    def testSubstitutesNamedArguments(self):
        request = TextFrame("p {power:0.3f}\r", r"p ([0-9.]+)\r",
                              fields={"power": float})
        self.assertEqual(request.encode(power=0.5), b"p 0.500\r")

    def testWhateverEndsTheLineIsVisibleInTheTemplate(self):
        self.assertEqual(TextFrame("*GWL", r"\*GWL").encode(), b"*GWL")
        self.assertEqual(TextFrame("g r0xc9\n", "g r0xc9\n").encode(), b"g r0xc9\n")
        self.assertEqual(TextFrame("SYST:ERR?\r\n", r"SYST:ERR\?\r\n").encode(),
                         b"SYST:ERR?\r\n")

    def testNamesTheArgumentsItNeeds(self):
        request = TextFrame("s r{register} {value}\r", r"s r(\S+) (-?\d+)\r",
                              fields={"register": str, "value": int})
        self.assertEqual(request.arguments, ("register", "value"))

    def testAMissingArgumentSaysWhichOne(self):
        with self.assertRaises(MissingArgument) as raised:
            TextFrame("p {power:0.3f}\r", r"p ([0-9.]+)\r").encode()
        self.assertIn("power", str(raised.exception))


class TestBinaryFrameWritingAFrame(unittest.TestCase):
    def testPacksConstantsOnly(self):
        request = BinaryFrame("<cc", fields=("header", "terminator"),
                                constants={"header": b"C", "terminator": b"\r"})
        self.assertEqual(request.encode(), b"C\r")
        self.assertEqual(request.arguments, ())

    def testPacksNamedValuesBetweenConstants(self):
        request = BinaryFrame(
            "<clllc", fields=("header", "x", "y", "z", "terminator"),
            constants={"header": b"M", "terminator": b"\r"})
        self.assertEqual(request.arguments, ("x", "y", "z"))
        self.assertEqual(request.encode(x=1, y=2, z=3),
                         pack("<clllc", b"M", 1, 2, 3, b"\r"))

    def testAMissingArgumentSaysWhichOne(self):
        request = BinaryFrame("<clllc", fields=("header", "x", "y", "z", "terminator"),
                                constants={"header": b"M", "terminator": b"\r"})
        with self.assertRaises(MissingArgument) as raised:
            request.encode(x=1, y=2)
        self.assertIn("z", str(raised.exception))

    def testAValueOfTheWrongKindIsRefusedWithItsFormat(self):
        request = BinaryFrame("<l", fields=("steps",))
        with self.assertRaises(ProtocolError) as raised:
            request.encode(steps="far")
        self.assertIn("<l", str(raised.exception))


class TestTextFrameReadingALine(unittest.TestCase):
    def testDecodesNamedGroupsThroughTheirConverters(self):
        reply = TextFrame("{power:0.3f}\r\n", r"(\d+\.\d+)", fields={"power": float})
        self.assertEqual(reply.decode(b"0.123\r\n"), {"power": 0.123})

    def testDecodesSeveralFieldsInGroupOrder(self):
        reply = TextFrame("v {position} {status}\r", r"v\s(-?\d+)\s(\d+)",
                          fields={"position": int, "status": int})
        self.assertEqual(reply.decode("v -42 3"), {"position": -42, "status": 3})

    def testAnAcknowledgementCarriesNoValues(self):
        self.assertEqual(TextFrame("OK\r\n", "OK").decode(b"OK\r\n"), {})

    def testAReplyThatDoesNotMatchRaisesWithBothSides(self):
        reply = TextFrame("{power:0.3f}\r\n", r"(\d+\.\d+)", fields={"power": float})
        with self.assertRaises(DidNotMatch) as raised:
            reply.decode(b"syntax error\r\n")
        self.assertIn("syntax error", str(raised.exception))

    def testNamingTheWrongNumberOfFieldsIsCaught(self):
        reply = TextFrame("{only}\r", r"(\d+)\s(\d+)", fields={"only": int})
        with self.assertRaises(ProtocolError):
            reply.decode("1 2")

    def testItParsesWhateverItIsHanded(self):
        # Trailing bytes, or none, are the port's business: the same description
        # reads a line however that line happened to arrive.
        reply = TextFrame("{power:0.3f}\r\n", r"(\d+\.\d+)", fields={"power": float})
        for arrival in (b"0.123\r\n", b"0.123\n", b"0.123\r", b"0.123", "0.123"):
            self.assertEqual(reply.decode(arrival), {"power": 0.123})
        self.assertIsNone(reply.readLength)

    def testTheTemplateSaysWhatTheRegexLeavesOut(self):
        # The regex matches with or without the terminator, because re.search does
        # not care what follows. The template has to be exact: it is what a mock
        # actually puts on the wire.
        reply = TextFrame("OK\r\n", "OK")
        self.assertEqual(reply.encode(), b"OK\r\n")
        self.assertEqual(reply.decode(reply.encode()), {})


class TestBinaryFrameReadingAFrame(unittest.TestCase):
    def testLengthComesFromTheFormat(self):
        self.assertEqual(BinaryFrame("<lllx", fields=("x", "y", "z")).readLength, 13)
        self.assertEqual(BinaryFrame("<c").readLength, 1)

    def testDecodesEachFieldByName(self):
        reply = BinaryFrame("<lllx", fields=("x", "y", "z"))
        self.assertEqual(reply.decode(pack("<lllc", 100, 200, 300, b"\r")),
                         {"x": 100, "y": 200, "z": 300})

    def testAShortFrameSaysWhatWasExpected(self):
        reply = BinaryFrame("<lllx", fields=("x", "y", "z"))
        with self.assertRaises(DidNotMatch) as raised:
            reply.decode(b"\x01\x02")
        self.assertIn("13", str(raised.exception))

    def testNamingTheWrongNumberOfFieldsIsCaught(self):
        reply = BinaryFrame("<ll", fields=("only",))
        with self.assertRaises(ProtocolError):
            reply.decode(pack("<ll", 1, 2))

    def testItSaysHowManyBytesToRead(self):
        # The one thing a caller cannot work out for itself: a fixed-size frame
        # has no terminator to stop at.
        self.assertEqual(BinaryFrame("<c").readLength, 1)
        self.assertEqual(BinaryFrame("<lllx", fields=("x", "y", "z")).readLength, 13)


class TestByteOrderMustBeExplicit(unittest.TestCase):
    def testAFormatWithoutAPrefixIsRefused(self):
        with self.assertRaises(ProtocolError) as raised:
            BinaryFrame("clllc", fields=("header", "x", "y", "z", "terminator"))
        message = str(raised.exception)
        self.assertIn("14", message)          # what the instrument expects
        self.assertIn("<clllc", message)      # and how to say it

    def testTheReplySideIsGuardedToo(self):
        with self.assertRaises(ProtocolError):
            BinaryFrame("lllx", fields=("x", "y", "z"))

    def testEveryExplicitPrefixIsAccepted(self):
        for prefix in ("<", ">", "!", "="):
            self.assertEqual(BinaryFrame(prefix + "l", fields=("value",)).readLength, 4)

    def testWithoutTheGuardTheLengthWouldBeWrong(self):
        # What is actually being prevented: not a crash, a wrong frame.
        self.assertEqual(calcsize("<clllc"), 14)
        self.assertNotEqual(calcsize("clllc"), 14)


def getPowerCommand() -> Command:
    """Build the Cobolt power query, stated in full: both halves, both directions.

    Returns:
        A fresh command each call, so that a test cannot be affected by what
        another did to it.
    """
    return Command("GET_POWER",
                   TextFrame("pa?\r", r"pa\?\r"),
                   TextFrame("{power:0.4f}\r\n", r"(\d+\.\d+)", fields={"power": float}))


class TestCommand(unittest.TestCase):
    def testCarriesARequestAndItsReply(self):
        command = getPowerCommand()
        self.assertEqual(command.encode(), b"pa?\r")
        self.assertEqual(command.decode(b"0.250\r\n"), {"power": 0.25})
        self.assertTrue(command.expectsReply)

    def testACommandMayExpectNothingBack(self):
        command = Command("SET_WAVELENGTH",
                          TextFrame("*PWC{wavelength:05d}", r"\*PWC(\d{5})",
                                      fields={"wavelength": int}))
        self.assertFalse(command.expectsReply)
        self.assertEqual(command.encode(wavelength=532), b"*PWC00532")
        with self.assertRaises(ProtocolError):
            command.decode(b"anything")

    def testTheDescriptionIsSharedButTheResultIsNot(self):
        # The point of the whole exercise: two callers of one description cannot
        # overwrite each other, because nothing is stored on it.
        command = getPowerCommand()
        first = command.decode(b"0.100\r\n")
        second = command.decode(b"0.900\r\n")
        self.assertEqual(first, {"power": 0.1})
        self.assertEqual(second, {"power": 0.9})
        self.assertEqual(vars(command).keys(), {"name", "request", "reply"})

    def testAFrameSaysOnlyThatItDidNotMatchAndTheCommandSaysWhichHalf(self):
        # A frame has no idea which command it belongs to, or which end of it, so
        # naming both is the command's job -- and it is the reason there is no
        # request class and no reply class to carry that name instead.
        command = getPowerCommand()
        with self.assertRaises(ReplyDidNotMatch) as raised:
            command.decode(b"syntax error\r\n")
        self.assertIn("GET_POWER", str(raised.exception))
        self.assertIn("syntax error", str(raised.exception))

        with self.assertRaises(RequestDidNotMatch) as raised:
            command.decodeRequest(b"l?\r")
        self.assertIn("GET_POWER", str(raised.exception))

    def testOneFrameCanServeEitherHalf(self):
        # Nothing marks a frame as a request or a reply: an instrument that echoes
        # its own line back is described once and put in both slots.
        line = TextFrame("OK\r\n", "OK")
        echo = Command("ECHO", line, line)
        self.assertEqual(echo.encode(), echo.encodeReply())
        self.assertEqual(echo.decodeRequest(b"OK\r\n"), echo.decode(b"OK\r\n"))


class TestTheMirrorDirection(unittest.TestCase):
    """Reading a request and writing a reply: the same descriptions, other way round."""

    def testWhatATemplateWroteItsRegexReadsBack(self):
        # The two notations are written separately and have to agree. Nothing
        # enforces that but a round trip, which is why every command here has one.
        request = TextFrame("p {power:0.3f}\r", r"p ([0-9.]+)\r",
                              fields={"power": float})
        self.assertEqual(request.decode(request.encode(power=0.5)), {"power": 0.5})

    def testTheRegexSaysWhatEachFieldWasRatherThanTheFormatSpec(self):
        # A converter is named, not guessed from "05d" or "x". The description says
        # what comes back, so "0x24" stays text and 31 comes back an int because
        # each was asked for.
        wavelength = TextFrame("*PWC{wavelength:05d}", r"\*PWC(\d{5})",
                                 fields={"wavelength": int})
        self.assertEqual(wavelength.decode(b"*PWC00532"), {"wavelength": 532})

        register = TextFrame("s r{register} {value}\r", r"s r(\S+) (-?\d+)\r",
                               fields={"register": str, "value": int})
        self.assertEqual(register.decode(register.encode(register="0x24", value=31)),
                         {"register": "0x24", "value": 31})

    def testARequestThatBelongsToAnotherCommandIsDeclined(self):
        with self.assertRaises(DidNotMatch):
            TextFrame("pa?\r", r"pa\?\r").decode(b"l?\r")

    def testABinaryRequestGivesBackOnlyWhatWasNotConstant(self):
        request = BinaryFrame("<clllc", fields=("header", "x", "y", "z", "terminator"),
                                constants={"header": b"M", "terminator": b"\r"})
        self.assertEqual(request.decode(request.encode(x=1, y=2, z=3)),
                         {"x": 1, "y": 2, "z": 3})

    def testABinaryConstantIsRequiredOnTheWayIn(self):
        request = BinaryFrame("<cc", fields=("header", "terminator"),
                                constants={"header": b"C", "terminator": b"\r"})
        with self.assertRaises(DidNotMatch) as raised:
            request.decode(b"H\r")
        self.assertIn("header", str(raised.exception))

    def testAConstantMustNameAFieldThatExists(self):
        with self.assertRaises(BadDescription) as raised:
            BinaryFrame("<cc", fields=("header", "terminator"),
                          constants={"heder": b"C"})
        self.assertIn("heder", str(raised.exception))

    def testATextReplyWritesTheLineItMatches(self):
        reply = TextFrame("{power:0.4f}\r\n", r"(\d+\.\d+)", fields={"power": float})
        self.assertEqual(reply.encode(power=0.0499), b"0.0499\r\n")
        self.assertEqual(reply.decode(reply.encode(power=0.0499)), {"power": 0.0499})

    def testACommandWithNoReplyHasNothingToAnswer(self):
        command = Command("SET_WAVELENGTH",
                          TextFrame("*PWC{wavelength:05d}", r"\*PWC(\d{5})",
                                      fields={"wavelength": int}))
        with self.assertRaises(ProtocolError):
            command.encodeReply()

    def testTheWholeLoopOverOneCoboltCommand(self):
        # Driver writes, mock recognises, mock answers, driver reads -- four steps
        # and one description.
        cobolt = CommandDictionary.fromJSON(COBOLT)
        sent = cobolt["SET_POWER"].encode(power=0.05)

        command, arguments = cobolt.recognize(sent)
        self.assertEqual(command.name, "SET_POWER")
        self.assertEqual(arguments, {"power": 0.05})

        answered = command.encodeReply()
        self.assertEqual(answered, b"OK\r\n")
        self.assertEqual(cobolt["SET_POWER"].decode(answered), {})

    def testEveryCoboltCommandGoesBothWays(self):
        cobolt = CommandDictionary.fromJSON(COBOLT)
        for name, arguments, answer in (
                ("GET_POWER", {}, {"power": 0.0499}),
                ("SET_POWER", {"power": 0.05}, {}),
                ("GET_ON_OFF", {}, {"isOn": True}),
                ("TURN_ON", {}, {})):
            command = cobolt[name]
            recognised, readBack = cobolt.recognize(command.encode(**arguments))
            self.assertEqual(recognised.name, name)
            self.assertEqual(readBack, arguments)
            self.assertEqual(command.decode(command.encodeReply(**answer)), answer)


class TestItCanExpressTheProtocolsWeAlreadyHave(unittest.TestCase):
    """The real test of the design: say what the drivers in this repo actually speak."""

    def testCoboltSetAndReadPower(self):
        setPower = Command("SET_POWER",
                           TextFrame("p {power:0.3f}\r", r"p ([0-9.]+)\r",
                                       fields={"power": float}),
                           TextFrame("OK\r\n", "OK"))
        self.assertEqual(setPower.encode(power=0.05), b"p 0.050\r")
        self.assertEqual(setPower.decode(b"OK\r\n"), {})
        self.assertEqual(setPower.decodeRequest(b"p 0.050\r"), {"power": 0.05})

        getPower = Command("GET_POWER", TextFrame("pa?\r", r"pa\?\r"),
                           TextFrame("{power:0.4f}\r\n", r"(\d+\.\d+)",
                                     fields={"power": float}))
        self.assertEqual(getPower.encode(), b"pa?\r")
        self.assertEqual(getPower.decode(b"0.0499\r\n"), {"power": 0.0499})
        self.assertEqual(getPower.encodeReply(power=0.0499), b"0.0499\r\n")

    def testCoboltOnOffStateAsABoolean(self):
        getOnOff = Command("GET_ON_OFF", TextFrame("l?\r", r"l\?\r"),
                           TextFrame("{isOn:d}\r\n", r"(0|1)",
                                     fields={"isOn": lambda text: text == "1"}))
        self.assertEqual(getOnOff.decode(b"1\r\n"), {"isOn": True})
        self.assertEqual(getOnOff.decode(b"0\r\n"), {"isOn": False})
        self.assertEqual(getOnOff.encodeReply(isOn=True), b"1\r\n")
        self.assertEqual(getOnOff.encodeReply(isOn=False), b"0\r\n")

    def testSutterMoveAndPosition(self):
        move = Command(
            "MOVE",
            BinaryFrame("<clllc", fields=("header", "x", "y", "z", "terminator"),
                          constants={"header": b"M", "terminator": b"\r"}),
            BinaryFrame("<c", fields=("acknowledgement",)))
        self.assertEqual(move.encode(x=4000, y=5000, z=6000),
                         pack("<clllc", b"M", 4000, 5000, 6000, b"\r"))
        self.assertEqual(move.decode(b"\r"), {"acknowledgement": b"\r"})

        position = Command(
            "GET_POSITION",
            BinaryFrame("<cc", fields=("header", "terminator"),
                          constants={"header": b"C", "terminator": b"\r"}),
            BinaryFrame("<lllx", fields=("x", "y", "z")))
        self.assertEqual(position.encode(), b"C\r")
        self.assertEqual(position.reply.readLength, 13)
        self.assertEqual(position.decode(pack("<lllc", 1, 2, 3, b"\r")),
                         {"x": 1, "y": 2, "z": 3})

    def testIntegraWavelengthBothWays(self):
        getWavelength = Command(
            "GETWAVELENGTH", TextFrame("*GWL", r"\*GWL"),
            TextFrame("PWC : {wavelength}\r\n", r"PWC\s*:\s*(.+?)\r\n",
                      fields={"wavelength": float}))
        self.assertEqual(getWavelength.encode(), b"*GWL")
        self.assertEqual(getWavelength.decode(b"PWC : 532.0\r\n"), {"wavelength": 532.0})
        self.assertEqual(getWavelength.encodeReply(wavelength=532.0), b"PWC : 532.0\r\n")

        setWavelength = Command(
            "SETWAVELENGTH",
            TextFrame("*PWC{wavelength:05d}", r"\*PWC(\d{5})",
                        fields={"wavelength": int}))
        self.assertEqual(setWavelength.encode(wavelength=1064), b"*PWC01064")
        self.assertEqual(setWavelength.decodeRequest(b"*PWC01064"), {"wavelength": 1064})

    def testIntellidriveRegisters(self):
        setRegister = Command(
            "SET_REGISTER",
            TextFrame("s r{register} {value}\r", r"s r(\S+) (-?\d+)\r",
                        fields={"register": str, "value": int}),
            TextFrame("ok\r", "ok"))
        self.assertEqual(setRegister.encode(register="0x24", value=31), b"s r0x24 31\r")
        self.assertEqual(setRegister.decode(b"ok\r"), {})
        self.assertEqual(setRegister.decodeRequest(b"s r0x24 31\r"),
                         {"register": "0x24", "value": 31})

        getRegister = Command(
            "GET_REGISTER",
            TextFrame("g r{register}\n", r"g r(\S+)\n", fields={"register": str}),
            TextFrame("v {value}\r", r"v\s(-?\d+)", fields={"value": int}))
        self.assertEqual(getRegister.encode(register="0xc9"), b"g r0xc9\n")
        self.assertEqual(getRegister.decode(b"v -1234\r"), {"value": -1234})
        self.assertEqual(getRegister.encodeReply(value=-1234), b"v -1234\r")

    def testTheSR830SnapReplyThatHasNoDescriptionToday(self):
        # SNAP? returns several comma-separated floats at one instant; the current
        # Command cannot say that at all, so SR830Device parses it by hand.
        snap = Command(
            "SNAP", TextFrame("SNAP? 1,2,3,4\n", r"SNAP\? 1,2,3,4\n"),
            TextFrame("{x:.4g},{y:.4g},{magnitude:.4g},{phase:.4g}\r\n",
                      r"([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+)",
                      fields={"x": float, "y": float,
                              "magnitude": float, "phase": float}))
        self.assertEqual(snap.encode(), b"SNAP? 1,2,3,4\n")
        measured = {"x": 0.001, "y": -0.002, "magnitude": 0.002236, "phase": -63.4}
        self.assertEqual(snap.decode(b"1.0e-3,-2.0e-3,2.236e-3,-63.4\r\n"), measured)
        self.assertEqual(snap.decode(snap.encodeReply(**measured)), measured)


COBOLT = """
{
  "device": "Cobolt laser",
  "commands": {
    "GET_POWER": {
      "request": {"template": "pa?\\r", "regex": "pa\\\\?\\r"},
      "reply":   {"regex": "(\\\\d+\\\\.\\\\d+)", "template": "{power:0.4f}\\r\\n",
                  "fields": {"power": "float"}}
    },
    "SET_POWER": {
      "request": {"template": "p {power:0.3f}\\r", "regex": "p ([0-9.]+)\\r",
                  "fields": {"power": "float"}},
      "reply":   {"regex": "OK", "template": "OK\\r\\n"}
    },
    "GET_ON_OFF": {
      "request": {"template": "l?\\r", "regex": "l\\\\?\\r"},
      "reply":   {"regex": "(0|1)", "template": "{isOn:d}\\r\\n",
                  "fields": {"isOn": "boolean01"}}
    },
    "TURN_ON": {
      "request": {"template": "l1\\r", "regex": "l1\\r"},
      "reply":   {"regex": "OK", "template": "OK\\r\\n"}
    }
  }
}
"""

SUTTER = """
{
  "device": "Sutter MP-285",
  "commands": {
    "MOVE": {
      "request": {"struct": "<clllc",
                  "fields": ["header", "x", "y", "z", "terminator"],
                  "constants": {"header": "M", "terminator": "\\r"}},
      "reply":   {"struct": "<c", "fields": ["acknowledgement"],
                  "constants": {"acknowledgement": "\\r"}}
    },
    "GET_POSITION": {
      "request": {"struct": "<cc", "fields": ["header", "terminator"],
                  "constants": {"header": "C", "terminator": "\\r"}},
      "reply":   {"struct": "<lllc", "fields": ["x", "y", "z", "terminator"],
                  "constants": {"terminator": "\\r"}}
    },
    "HOME": {
      "request": {"struct": "<cc", "fields": ["header", "terminator"],
                  "constants": {"header": "H", "terminator": "\\r"}},
      "reply":   {"struct": "<c", "fields": ["acknowledgement"],
                  "constants": {"acknowledgement": "\\r"}}
    },
    "WORK": {
      "request": {"struct": "<cc", "fields": ["header", "terminator"],
                  "constants": {"header": "Y", "terminator": "\\r"}},
      "reply":   {"struct": "<c", "fields": ["acknowledgement"],
                  "constants": {"acknowledgement": "\\r"}}
    }
  }
}
"""


class TestCommandDictionary(unittest.TestCase):
    def setUp(self):
        self.cobolt = CommandDictionary.fromJSON(COBOLT)
        self.sutter = CommandDictionary.fromJSON(SUTTER)

    def testItReadsLikeADictionaryOfCommands(self):
        self.assertEqual(len(self.cobolt), 4)
        self.assertIn("GET_POWER", self.cobolt)
        self.assertEqual(sorted(self.cobolt.names),
                         ["GET_ON_OFF", "GET_POWER", "SET_POWER", "TURN_ON"])
        self.assertIsInstance(self.cobolt["GET_POWER"], Command)
        self.assertEqual(self.cobolt.deviceName, "Cobolt laser")

    def testATextCommandFromAFileBehavesLikeOneWrittenByHand(self):
        fromFile = self.cobolt["SET_POWER"]
        byHand = Command("SET_POWER",
                         TextFrame("p {power:0.3f}\r", r"p ([0-9.]+)\r",
                                     fields={"power": float}),
                         TextFrame("OK\r\n", "OK"))
        self.assertEqual(fromFile.encode(power=0.05), byHand.encode(power=0.05))
        self.assertEqual(fromFile.decode(b"OK\r\n"), byHand.decode(b"OK\r\n"))
        self.assertEqual(fromFile.decodeRequest(b"p 0.050\r"),
                         byHand.decodeRequest(b"p 0.050\r"))
        self.assertEqual(fromFile.encodeReply(), byHand.encodeReply())

    def testABinaryCommandFromAFileBehavesLikeOneWrittenByHand(self):
        # The point of the whole layer: JSON adds notation, not behaviour.
        fromFile = self.sutter["MOVE"]
        byHand = Command(
            "MOVE",
            BinaryFrame("<clllc", fields=("header", "x", "y", "z", "terminator"),
                          constants={"header": b"M", "terminator": b"\r"}),
            BinaryFrame("<c", fields=("acknowledgement",)))
        self.assertEqual(fromFile.encode(x=4000, y=5000, z=6000),
                         byHand.encode(x=4000, y=5000, z=6000))
        self.assertEqual(fromFile.encode(x=4000, y=5000, z=6000),
                         pack("<clllc", b"M", 4000, 5000, 6000, b"\r"))

    def testConvertersAreNamedInTheFileAndResolvedHere(self):
        self.assertEqual(self.cobolt["GET_POWER"].decode(b"0.0499\r\n"), {"power": 0.0499})
        self.assertEqual(self.cobolt["GET_ON_OFF"].decode(b"1\r\n"), {"isOn": True})
        self.assertEqual(self.cobolt["GET_ON_OFF"].decode(b"0\r\n"), {"isOn": False})

    def testABinaryReplyStillReportsItsLength(self):
        self.assertEqual(self.sutter["GET_POSITION"].reply.readLength, 13)
        self.assertEqual(self.sutter["GET_POSITION"].decode(pack("<lllc", 1, 2, 3, b"\r")),
                         {"x": 1, "y": 2, "z": 3})

    def testAConstantByteSurvivesTheFile(self):
        self.assertEqual(self.sutter["GET_POSITION"].encode(), b"C\r")

    def testAnUnknownCommandSaysWhatTheDeviceDoesHave(self):
        with self.assertRaises(KeyError) as raised:
            self.cobolt["GETPOWR"]
        message = str(raised.exception)
        self.assertIn("Cobolt laser", message)
        self.assertIn("GET_POWER", message)

    def testItLoadsFromAFileOnDisk(self):
        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        try:
            with open(path, "w") as file:
                file.write(COBOLT)
            fromDisk = CommandDictionary.fromFile(path)
            self.assertEqual(sorted(fromDisk.names), sorted(self.cobolt.names))
            self.assertEqual(fromDisk["TURN_ON"].encode(), b"l1\r")
        finally:
            os.remove(path)


class TestTheWholeSutterProtocol(unittest.TestCase):
    """Everything the commands dict in motion/sutterdevice.py says, said here.

    The expected bytes are the ones that dict produces today, so a failure means
    the description drifted from the driver rather than the driver changing.
    """

    def setUp(self):
        self.sutter = CommandDictionary.fromJSON(SUTTER)

    def testItDescribesEveryCommandTheDriverHas(self):
        self.assertEqual(sorted(self.sutter.names),
                         ["GET_POSITION", "HOME", "MOVE", "WORK"])

    def testMoveCarriesThreePositionsBetweenItsHeaderAndItsReturn(self):
        move = self.sutter["MOVE"]
        self.assertEqual(move.request.arguments, ("x", "y", "z"))
        self.assertEqual(move.encode(x=4000, y=5000, z=6000),
                         pack("<clllc", b"M", 4000, 5000, 6000, b"\r"))
        self.assertEqual(move.decode(b"\r"), {})

    def testGetPositionAsksWithTwoBytesAndIsAnsweredWithThirteen(self):
        position = self.sutter["GET_POSITION"]
        self.assertEqual(position.encode(), pack("<cc", b"C", b"\r"))
        self.assertEqual(position.reply.readLength, 13)
        self.assertEqual(position.decode(pack("<lllc", 16000, 32000, 48000, b"\r")),
                         {"x": 16000, "y": 32000, "z": 48000})

    def testHomeAndWorkDifferOnlyByOneHeaderByte(self):
        self.assertEqual(self.sutter["HOME"].encode(), pack("<cc", b"H", b"\r"))
        self.assertEqual(self.sutter["WORK"].encode(), pack("<cc", b"Y", b"\r"))
        for name in ("GET_POSITION", "HOME", "WORK"):
            self.assertEqual(self.sutter[name].request.arguments, ())

    def testTheAcknowledgementIsRequiredRatherThanReturned(self):
        # sutterdevice.py checks this by hand three times, at :102, :115 and :121,
        # because the old dict could not say it. Now the description says it, and a
        # fixed byte carries no information, so it is not handed back either.
        for name in ("MOVE", "HOME", "WORK"):
            self.assertEqual(self.sutter[name].decode(b"\r"), {})
            with self.assertRaises(ReplyDidNotMatch):
                self.sutter[name].decode(b"X")

    def testTheMockAnswersWithTheSameDescriptionTheDriverSendsWith(self):
        # The old dict needed '<lllx' to read a position and '<lllc' to write one,
        # two formats for the same thirteen bytes. Naming the terminator instead of
        # padding it over leaves one format that works in both directions.
        position = self.sutter["GET_POSITION"]
        self.assertEqual(position.reply.struct, "<lllc")
        self.assertEqual(position.encodeReply(x=16000, y=32000, z=48000),
                         pack("<lllc", 16000, 32000, 48000, b"\r"))
        self.assertEqual(position.decode(position.encodeReply(x=1, y=2, z=3)),
                         {"x": 1, "y": 2, "z": 3})

    def testAMockRecognisesEachRequestByItsHeader(self):
        # What DataDecoder(prefix=b'M') said separately, read off the constants the
        # request already declares.
        for name, sent in (("HOME", b"H\r"), ("WORK", b"Y\r"), ("GET_POSITION", b"C\r")):
            command, arguments = self.sutter.recognize(sent)
            self.assertEqual(command.name, name)
            self.assertEqual(arguments, {})

        command, arguments = self.sutter.recognize(
            pack("<clllc", b"M", 4000, 5000, 6000, b"\r"))
        self.assertEqual(command.name, "MOVE")
        self.assertEqual(arguments, {"x": 4000, "y": 5000, "z": 6000})

    def testAnUnknownRequestIsRefusedByName(self):
        with self.assertRaises(RequestDidNotMatch) as raised:
            self.sutter.recognize(b"Z\r")
        self.assertIn("Sutter MP-285", str(raised.exception))


class TestItExplainsItself(unittest.TestCase):
    """What someone reads before writing the first call to a device."""

    def setUp(self):
        self.cobolt = CommandDictionary.fromJSON(COBOLT).usage()
        self.sutter = CommandDictionary.fromJSON(SUTTER).usage()

    def testItNamesTheDeviceAndEveryCommandInTheOrderTheFileListedThem(self):
        self.assertIn("Cobolt laser: 4 commands", self.cobolt)
        self.assertLess(self.cobolt.index("GET_POWER"), self.cobolt.index("TURN_ON"))

    def testAnArgumentIsShownWithItsType(self):
        self.assertIn("SET_POWER(power: float)", self.cobolt)

    def testWhatComesBackIsShownWithItsType(self):
        self.assertIn("answers power: float", self.cobolt)

    def testAConverterIsShownByWhatItReturnsRatherThanItsOwnName(self):
        self.assertIn("answers isOn: bool", self.cobolt)

    def testABinaryFrameTakesItsTypesFromTheStruct(self):
        self.assertIn("MOVE(x: int32, y: int32, z: int32)", self.sutter)
        self.assertIn("answers x: int32, y: int32, z: int32", self.sutter)

    def testAConstantIsNotSomethingToPassNorSomethingToRead(self):
        # header and terminator are in every Sutter frame and in nobody's call.
        self.assertIn("GET_POSITION()", self.sutter)
        self.assertNotIn("header", self.sutter)
        self.assertNotIn("terminator", self.sutter)

    def testAnAcknowledgementIsSaidToCarryNothing(self):
        self.assertIn("HOME()\n      answers, carrying no values", self.sutter)

    def testACommandTheInstrumentIgnoresSaysSo(self):
        integra = CommandDictionary(
            {"SETWAVELENGTH": Command(
                "SETWAVELENGTH",
                TextFrame("*PWC{wavelength:05d}", r"\*PWC(\d{5})",
                            fields={"wavelength": int}))},
            deviceName="Integra")
        self.assertIn("SETWAVELENGTH(wavelength: int)", integra.usage())
        self.assertIn("the instrument does not answer", integra.usage())

    def testPrintingTheDictionaryExplainsIt(self):
        cobolt = CommandDictionary.fromJSON(COBOLT)
        self.assertEqual(str(cobolt), cobolt.usage())

    def testPaddingAndRepeatsDoNotThrowTheTypesOutOfLine(self):
        codesOf = BinaryFrame.structCodes
        self.assertEqual(codesOf("<clllc"), ("c", "l", "l", "l", "c"))
        self.assertEqual(codesOf("<lllx"), ("l", "l", "l"))
        self.assertEqual(codesOf("<3l"), ("l", "l", "l"))
        self.assertEqual(codesOf("<10s"), ("s",))


class TestTheFileAndTheObjectsSpeakOneVocabulary(unittest.TestCase):
    """A key in the description and the attribute it becomes are the same word.

    Without this, the two halves drift: the file said "template" while the object
    said something else, and a reader had to learn both.
    """

    def testTextIsATemplateOutAndARegexBack(self):
        command = CommandDictionary.fromJSON(COBOLT)["GET_POWER"]
        self.assertEqual(command.request.template, "pa?\r")
        self.assertEqual(command.reply.regex, r"(\d+\.\d+)")

    def testBinaryIsAStructInBothDirections(self):
        command = CommandDictionary.fromJSON(SUTTER)["MOVE"]
        self.assertEqual(command.request.struct, "<clllc")
        self.assertEqual(command.reply.struct, "<c")


class TestADescriptionThatDoesNotMakeSense(unittest.TestCase):
    def buildFrom(self, commands):
        return CommandDictionary.fromDescription({"device": "test", "commands": commands})

    def testACommandWithoutARequest(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"NOWHERE": {"reply": {"regex": "OK"}}})
        self.assertIn("NOWHERE", str(raised.exception))

    def testARequestThatIsNeitherTextNorBinary(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"ODD": {"request": {"bytes": "M"}}})
        self.assertIn("template", str(raised.exception))
        self.assertIn("struct", str(raised.exception))

    def testAReplyThatIsNeitherTextNorBinary(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"ODD": {"request": {"template": "r?\r", "regex": r"r\?\r"},
                                    "reply": {"bytes": "OK"}}})
        self.assertIn("regex", str(raised.exception))
        self.assertIn("struct", str(raised.exception))

    def testATextRequestThatOnlyKnowsHowToBeWritten(self):
        # Half a description is not a description: a mock could never read this.
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"HALF": {"request": {"template": "r?\r"}}})
        self.assertIn("HALF", str(raised.exception))
        self.assertIn("regex", str(raised.exception))

    def testATextReplyThatOnlyKnowsHowToBeRead(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"HALF": {"request": {"template": "r?\r", "regex": r"r\?\r"},
                                     "reply": {"regex": "OK"}}})
        self.assertIn("HALF", str(raised.exception))
        self.assertIn("template", str(raised.exception))

    def testAConverterThatDoesNotExist(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"READ": {"request": {"template": "r?\r", "regex": r"r\?\r"},
                                     "reply": {"regex": "(.+)", "template": "{value}\r",
                                               "fields": {"value": "decimal"}}}})
        message = str(raised.exception)
        self.assertIn("decimal", message)
        self.assertIn("float", message)      # names the ones that do exist

    def testTheByteOrderGuardStillFiresThroughTheFile(self):
        # A description is not a way around the checks the objects make.
        with self.assertRaises(ProtocolError) as raised:
            self.buildFrom({"MOVE": {"request": {"struct": "clllc",
                                                 "fields": ["header", "x", "y", "z", "terminator"]}}})
        self.assertIn("<clllc", str(raised.exception))

    def testADescriptionWithNoCommandsAtAll(self):
        with self.assertRaises(BadDescription):
            CommandDictionary.fromDescription({"device": "test"})


if __name__ == "__main__":
    unittest.main()
