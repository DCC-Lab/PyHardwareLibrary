"""A prototype protocol description, developed in isolation inside its test file.

Nothing here is imported by the library, and nothing here touches a port: this is
a sketch of how an instrument protocol could be *described*, so the design can be
judged before any driver depends on it.

The idea is sans-I/O, the principle behind h11 and wsproto: the protocol is a pure
transformation over bytes and never performs the exchange. A Request turns named
arguments into the bytes to write; a Reply turns the bytes read back into named
values; neither owns a port, and neither stores what happened. That is what
separates this from the Command it would replace, which describes the protocol,
builds the bytes, performs the I/O, and then keeps the reply on itself -- on a
class attribute shared by every instance of a driver.

Consequences worth noticing while reading:

  - a description is immutable and shareable; the result of a command is a plain
    dict returned to the caller, so two instruments cannot overwrite each other;
  - a Reply parses whatever it is handed, and says how many bytes to read only
    where nothing else could know: a fixed-size binary frame;
  - decoding failure raises, naming what did not match, instead of being recorded
    in an attribute nobody checks.

Only the first half is built here: writing a request and decoding a reply. The
mirror image -- decoding a request and encoding a reply, which is what a
table-driven mock needs -- is deliberately left out.
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


# ---------------------------------------------------------------------------
# The prototype
# ---------------------------------------------------------------------------

class ProtocolError(Exception):
    """Base for anything the description itself can refuse."""


class MissingArgument(ProtocolError):
    """A request needs a value the caller did not supply."""


class ReplyDidNotMatch(ProtocolError):
    """The bytes read back are not what this reply describes."""


class BadDescription(ProtocolError):
    """A command description, usually read from a file, does not make sense."""


byteOrderPrefixes = ("<", ">", "!", "=")


def requireExplicitByteOrder(format: str):
    """Refuse a struct format that does not begin with a byte-order prefix.

    Without one, struct uses native sizes and native alignment: "clllc" is 33
    bytes on this machine rather than the 14 the instrument expects, an "l" is
    whatever a C long happens to be, and padding appears between the fields. The
    frame is then correct for the compiler and wrong for the wire, and nothing
    downstream would notice -- the same failure the ctypes variant needed
    _pack_ = 1 to avoid, at the price of one character here.
    """
    if not format.startswith(byteOrderPrefixes):
        raise ProtocolError(
            "{0!r} has no byte-order prefix, so struct would use native sizes and "
            "alignment: {1} bytes instead of {2}. Write {3!r}.".format(
                format, calcsize(format), calcsize("<" + format), "<" + format))


class Request(ABC):
    """How to turn named arguments into the bytes to write."""

    @abstractmethod
    def encode(self, **arguments) -> bytes:
        ...


class TextRequest(Request):
    """An ASCII request built from a format template.

    The template uses named fields, so a caller writes setPower(power=0.5) and
    never counts positional arguments: "p {power:0.3f}\r".

    Whatever ends the line is written into the template, where it can be seen,
    rather than passed alongside it: on the way out a terminator is simply more
    literal text, and instruments disagree about it enough -- \r, \n, \r\n, or
    nothing at all for the Integra -- that no default would serve.
    """

    def __init__(self, template: str):
        self.template = template

    @property
    def fields(self) -> tuple:
        """The argument names this request needs, in the order they appear."""
        return tuple(name for _, name, _, _ in string.Formatter().parse(self.template)
                     if name)

    def encode(self, **arguments) -> bytes:
        try:
            text = self.template.format(**arguments)
        except KeyError as error:
            raise MissingArgument("{0} needs {1}, got {2}".format(
                self.template, error, sorted(arguments))) from None
        return text.encode("utf-8")


class BinaryRequest(Request):
    """A packed binary request.

    fields names each value in the struct format, in order; constants are the ones
    the caller never supplies, such as a header byte or a trailing carriage return.
    """

    def __init__(self, format: str, fields: tuple = (), constants: dict = None):
        requireExplicitByteOrder(format)
        self.format = format
        self.fields = tuple(fields)
        self.constants = dict(constants or {})

    @property
    def arguments(self) -> tuple:
        """The names a caller must supply: every field that is not a constant."""
        return tuple(name for name in self.fields if name not in self.constants)

    def encode(self, **arguments) -> bytes:
        values = []
        for name in self.fields:
            if name in self.constants:
                values.append(self.constants[name])
            elif name in arguments:
                values.append(arguments[name])
            else:
                raise MissingArgument("{0} needs {1}, got {2}".format(
                    self.format, name, sorted(arguments)))
        try:
            return pack(self.format, *values)
        except StructError as error:
            raise ProtocolError("cannot pack {0} into {1}: {2}".format(
                values, self.format, error)) from None


class Reply(ABC):
    """How to turn the bytes read back into named values.

    Reading is the caller's business: a reply parses whatever it is handed. The
    one thing it must say is readLength, and only when nothing else could know it
    -- a fixed-size binary frame has no terminator to stop at, so the number of
    bytes to ask for can come from nowhere but the description. A line needs no
    such answer, since the port already reads up to its own terminator.
    """

    readLength = None

    @abstractmethod
    def decode(self, data: bytes) -> dict:
        ...


class TextReply(Reply):
    """A line matched by a regular expression.

    fields maps a name to the converter for its capture group, in group order:
    {"power": float} turns r"(\\d+\\.\\d+)" into {"power": 0.123}. A reply with no
    capture groups, such as an "OK" acknowledgement, decodes to an empty dict --
    it either matched or it raised.

    It parses whatever it is handed and says nothing about how to read it: where
    a line ends is the port's business, not the protocol's.
    """

    def __init__(self, pattern: str, fields: dict = None):
        self.pattern = pattern
        self.fields = dict(fields or {})

    def decode(self, data) -> dict:
        text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else data
        match = re.search(self.pattern, text)
        if match is None:
            raise ReplyDidNotMatch("expected {0!r}, got {1!r}".format(self.pattern, text))

        groups = match.groups()
        if len(groups) != len(self.fields):
            raise ProtocolError(
                "{0!r} captured {1} group(s) but {2} field(s) were named".format(
                    self.pattern, len(groups), len(self.fields)))
        return {name: converter(value)
                for (name, converter), value in zip(self.fields.items(), groups)}


class BinaryReply(Reply):
    """A fixed-size binary frame, named field by field.

    The struct format decides how many bytes to read, so readLength never has to
    be kept in step by hand. Padding in the format ('x') yields no value and so
    takes no field name.
    """

    def __init__(self, format: str, fields: tuple = ()):
        requireExplicitByteOrder(format)
        self.format = format
        self.fields = tuple(fields)

    @property
    def readLength(self) -> int:
        return calcsize(self.format)

    def decode(self, data) -> dict:
        if len(data) != self.readLength:
            raise ReplyDidNotMatch("expected {0} bytes for {1}, got {2}".format(
                self.readLength, self.format, len(data)))
        values = unpack(self.format, bytes(data))
        if len(values) != len(self.fields):
            raise ProtocolError(
                "{0} unpacks {1} value(s) but {2} field(s) were named".format(
                    self.format, len(values), len(self.fields)))
        return dict(zip(self.fields, values))


class Command:
    """One request and the reply it expects, named for a driver to call by name.

    A command is a description and nothing else: it says what to send and what
    should come back, and carries neither the data nor the transmission. encode()
    hands the caller the bytes to write, decode() turns what came back into
    values, and the port in between is the caller's.

    That is the whole difference from the Command this replaces, which described
    the protocol, built the bytes, performed the exchange, and then kept the
    reply on itself.
    """

    def __init__(self, name: str, request: Request, reply: Reply = None):
        self.name = name
        self.request = request
        self.reply = reply

    @property
    def expectsReply(self) -> bool:
        return self.reply is not None

    def encode(self, **arguments) -> bytes:
        return self.request.encode(**arguments)

    def decode(self, data) -> dict:
        if self.reply is None:
            raise ProtocolError("{0} expects no reply".format(self.name))
        return self.reply.decode(data)


class CommandDictionary:
    """Every command one device understands, by name, read from a file.

    A driver's protocol is a table, and a table is data: a description read from
    JSON builds the same objects a driver would write by hand, so a protocol can
    be read, reviewed and corrected without touching the code that speaks it.

    JSON rather than TOML or YAML because it is in the standard library of every
    Python the package supports; tomllib arrives only in 3.11, and YAML would be a
    dependency for a file nobody edits at runtime.

    A command is described by a request and, when there is one, a reply. Which key
    is present says which kind it is, so nothing declares a type twice:

        "GET_POWER": {
          "request": {"template": "pa?\r"},
          "reply":   {"pattern": "(\\d+\\.\\d+)", "fields": {"power": "float"}}
        },
        "MOVE": {
          "request": {"format": "<clllc",
                      "fields": ["header", "x", "y", "z", "terminator"],
                      "constants": {"header": "M", "terminator": "\r"}},
          "reply":   {"format": "<c", "fields": ["acknowledgement"]}
        }

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
        "boolean01": lambda text: text == "1",
        "hexInteger": lambda text: int(text, 16),
    }

    def __init__(self, commands: dict, deviceName: str = None):
        self.commands = dict(commands)
        self.deviceName = deviceName

    @classmethod
    def fromFile(cls, path: str) -> "CommandDictionary":
        """Read one device's commands from a JSON file."""
        with open(path, "r") as file:
            return cls.fromDescription(json.load(file))

    @classmethod
    def fromJSON(cls, text: str) -> "CommandDictionary":
        """Read them from JSON already in hand."""
        return cls.fromDescription(json.loads(text))

    @classmethod
    def fromDescription(cls, description: dict) -> "CommandDictionary":
        """Build from the description itself, however it was obtained."""
        if "commands" not in description:
            raise BadDescription("no commands: expected {'device': ..., 'commands': {...}}")
        return cls({name: cls.commandFrom(name, one)
                    for name, one in description["commands"].items()},
                   deviceName=description.get("device"))

    @classmethod
    def commandFrom(cls, name: str, description: dict) -> Command:
        """Build one named command from its description."""
        where = "command {0!r}".format(name)
        if "request" not in description:
            raise BadDescription("{0}: no request".format(where))
        reply = description.get("reply")
        return Command(name, cls.requestFrom(description["request"], where),
                       cls.replyFrom(reply, where) if reply is not None else None)

    @classmethod
    def requestFrom(cls, description: dict, where: str) -> Request:
        """Build the request half: a template for text, a format for binary."""
        if "template" in description:
            return TextRequest(description["template"])
        if "format" in description:
            return BinaryRequest(
                description["format"],
                fields=tuple(description.get("fields", ())),
                constants={name: cls.bytesFrom(value)
                           for name, value in description.get("constants", {}).items()})
        raise BadDescription(
            "{0}: a request needs a template, for text, or a format, for binary".format(where))

    @classmethod
    def replyFrom(cls, description: dict, where: str) -> Reply:
        """Build the reply half: a pattern for text, a format for binary."""
        if "pattern" in description:
            return TextReply(description["pattern"],
                             fields=cls.convertersFor(description.get("fields", {}), where))
        if "format" in description:
            return BinaryReply(description["format"],
                               fields=tuple(description.get("fields", ())))
        raise BadDescription(
            "{0}: a reply needs a pattern, for text, or a format, for binary".format(where))

    @classmethod
    def convertersFor(cls, fields: dict, where: str) -> dict:
        """Turn {"power": "float"} from a file into {"power": float}."""
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
        """A constant byte from a file, latin-1 so that \xfe stays one byte."""
        return text.encode("latin-1")

    @property
    def names(self) -> tuple:
        return tuple(self.commands)

    def __getitem__(self, name: str) -> Command:
        if name not in self.commands:
            raise KeyError("{0} has no command {1!r}; it has {2}".format(
                self.deviceName or "this device", name, ", ".join(sorted(self.commands))))
        return self.commands[name]

    def __contains__(self, name) -> bool:
        return name in self.commands

    def __iter__(self):
        return iter(self.commands)

    def __len__(self) -> int:
        return len(self.commands)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTextRequest(unittest.TestCase):
    def testBuildsAConstantRequest(self):
        self.assertEqual(TextRequest("pa?\r").encode(), b"pa?\r")

    def testSubstitutesNamedArguments(self):
        request = TextRequest("p {power:0.3f}\r")
        self.assertEqual(request.encode(power=0.5), b"p 0.500\r")

    def testWhateverEndsTheLineIsVisibleInTheTemplate(self):
        self.assertEqual(TextRequest("*GWL").encode(), b"*GWL")
        self.assertEqual(TextRequest("g r0xc9\n").encode(), b"g r0xc9\n")
        self.assertEqual(TextRequest("SYST:ERR?\r\n").encode(), b"SYST:ERR?\r\n")

    def testNamesTheFieldsItNeeds(self):
        self.assertEqual(TextRequest("s r{register} {value}\r").fields,
                         ("register", "value"))

    def testAMissingArgumentSaysWhichOne(self):
        with self.assertRaises(MissingArgument) as raised:
            TextRequest("p {power:0.3f}\r").encode()
        self.assertIn("power", str(raised.exception))


class TestBinaryRequest(unittest.TestCase):
    def testPacksConstantsOnly(self):
        request = BinaryRequest("<cc", fields=("header", "terminator"),
                                constants={"header": b"C", "terminator": b"\r"})
        self.assertEqual(request.encode(), b"C\r")
        self.assertEqual(request.arguments, ())

    def testPacksNamedValuesBetweenConstants(self):
        request = BinaryRequest(
            "<clllc", fields=("header", "x", "y", "z", "terminator"),
            constants={"header": b"M", "terminator": b"\r"})
        self.assertEqual(request.arguments, ("x", "y", "z"))
        self.assertEqual(request.encode(x=1, y=2, z=3),
                         pack("<clllc", b"M", 1, 2, 3, b"\r"))

    def testAMissingArgumentSaysWhichOne(self):
        request = BinaryRequest("<clllc", fields=("header", "x", "y", "z", "terminator"),
                                constants={"header": b"M", "terminator": b"\r"})
        with self.assertRaises(MissingArgument) as raised:
            request.encode(x=1, y=2)
        self.assertIn("z", str(raised.exception))

    def testAValueOfTheWrongKindIsRefusedWithItsFormat(self):
        request = BinaryRequest("<l", fields=("steps",))
        with self.assertRaises(ProtocolError) as raised:
            request.encode(steps="far")
        self.assertIn("<l", str(raised.exception))


class TestTextReply(unittest.TestCase):
    def testDecodesNamedGroupsThroughTheirConverters(self):
        reply = TextReply(r"(\d+\.\d+)", fields={"power": float})
        self.assertEqual(reply.decode(b"0.123\r\n"), {"power": 0.123})

    def testDecodesSeveralFieldsInGroupOrder(self):
        reply = TextReply(r"v\s(-?\d+)\s(\d+)", fields={"position": int, "status": int})
        self.assertEqual(reply.decode("v -42 3"), {"position": -42, "status": 3})

    def testAnAcknowledgementCarriesNoValues(self):
        self.assertEqual(TextReply("OK").decode(b"OK\r\n"), {})

    def testAReplyThatDoesNotMatchRaisesWithBothSides(self):
        reply = TextReply(r"(\d+\.\d+)", fields={"power": float})
        with self.assertRaises(ReplyDidNotMatch) as raised:
            reply.decode(b"syntax error\r\n")
        self.assertIn("syntax error", str(raised.exception))

    def testNamingTheWrongNumberOfFieldsIsCaught(self):
        reply = TextReply(r"(\d+)\s(\d+)", fields={"only": int})
        with self.assertRaises(ProtocolError):
            reply.decode("1 2")

    def testItParsesWhateverItIsHanded(self):
        # Trailing bytes, or none, are the port's business: the same description
        # reads a line however that line happened to arrive.
        reply = TextReply(r"(\d+\.\d+)", fields={"power": float})
        for arrival in (b"0.123\r\n", b"0.123\n", b"0.123\r", b"0.123", "0.123"):
            self.assertEqual(reply.decode(arrival), {"power": 0.123})
        self.assertIsNone(reply.readLength)


class TestBinaryReply(unittest.TestCase):
    def testLengthComesFromTheFormat(self):
        self.assertEqual(BinaryReply("<lllx", fields=("x", "y", "z")).readLength, 13)
        self.assertEqual(BinaryReply("<c").readLength, 1)

    def testDecodesEachFieldByName(self):
        reply = BinaryReply("<lllx", fields=("x", "y", "z"))
        self.assertEqual(reply.decode(pack("<lllc", 100, 200, 300, b"\r")),
                         {"x": 100, "y": 200, "z": 300})

    def testAShortFrameSaysWhatWasExpected(self):
        reply = BinaryReply("<lllx", fields=("x", "y", "z"))
        with self.assertRaises(ReplyDidNotMatch) as raised:
            reply.decode(b"\x01\x02")
        self.assertIn("13", str(raised.exception))

    def testNamingTheWrongNumberOfFieldsIsCaught(self):
        reply = BinaryReply("<ll", fields=("only",))
        with self.assertRaises(ProtocolError):
            reply.decode(pack("<ll", 1, 2))

    def testItSaysHowManyBytesToRead(self):
        # The one thing a caller cannot work out for itself: a fixed-size frame
        # has no terminator to stop at.
        self.assertEqual(BinaryReply("<c").readLength, 1)
        self.assertEqual(BinaryReply("<lllx", fields=("x", "y", "z")).readLength, 13)


class TestByteOrderMustBeExplicit(unittest.TestCase):
    def testAFormatWithoutAPrefixIsRefused(self):
        with self.assertRaises(ProtocolError) as raised:
            BinaryRequest("clllc", fields=("header", "x", "y", "z", "terminator"))
        message = str(raised.exception)
        self.assertIn("14", message)          # what the instrument expects
        self.assertIn("<clllc", message)      # and how to say it

    def testTheReplySideIsGuardedToo(self):
        with self.assertRaises(ProtocolError):
            BinaryReply("lllx", fields=("x", "y", "z"))

    def testEveryExplicitPrefixIsAccepted(self):
        for prefix in ("<", ">", "!", "="):
            self.assertEqual(BinaryReply(prefix + "l", fields=("value",)).readLength, 4)

    def testWithoutTheGuardTheLengthWouldBeWrong(self):
        # What is actually being prevented: not a crash, a wrong frame.
        self.assertEqual(calcsize("<clllc"), 14)
        self.assertNotEqual(calcsize("clllc"), 14)


class TestCommand(unittest.TestCase):
    def testCarriesARequestAndItsReply(self):
        command = Command("GET_POWER", TextRequest("pa?\r"),
                            TextReply(r"(\d+\.\d+)", fields={"power": float}))
        self.assertEqual(command.encode(), b"pa?\r")
        self.assertEqual(command.decode(b"0.250\r\n"), {"power": 0.25})
        self.assertTrue(command.expectsReply)

    def testACommandMayExpectNothingBack(self):
        command = Command("SET_WAVELENGTH", TextRequest("*PWC{wavelength:05d}"))
        self.assertFalse(command.expectsReply)
        self.assertEqual(command.encode(wavelength=532), b"*PWC00532")
        with self.assertRaises(ProtocolError):
            command.decode(b"anything")

    def testTheDescriptionIsSharedButTheResultIsNot(self):
        # The point of the whole exercise: two callers of one description cannot
        # overwrite each other, because nothing is stored on it.
        command = Command("GET_POWER", TextRequest("pa?\r"),
                            TextReply(r"(\d+\.\d+)", fields={"power": float}))
        first = command.decode(b"0.100\r\n")
        second = command.decode(b"0.900\r\n")
        self.assertEqual(first, {"power": 0.1})
        self.assertEqual(second, {"power": 0.9})
        self.assertEqual(vars(command).keys(), {"name", "request", "reply"})


class TestItCanExpressTheProtocolsWeAlreadyHave(unittest.TestCase):
    """The real test of the design: say what the drivers in this repo actually speak."""

    def testCoboltSetAndReadPower(self):
        setPower = Command("SET_POWER", TextRequest("p {power:0.3f}\r"), TextReply("OK"))
        self.assertEqual(setPower.encode(power=0.05), b"p 0.050\r")
        self.assertEqual(setPower.decode(b"OK\r\n"), {})

        getPower = Command("GET_POWER", TextRequest("pa?\r"),
                            TextReply(r"(\d+\.\d+)", fields={"power": float}))
        self.assertEqual(getPower.encode(), b"pa?\r")
        self.assertEqual(getPower.decode(b"0.0499\r\n"), {"power": 0.0499})

    def testCoboltOnOffStateAsABoolean(self):
        getOnOff = Command("GET_ON_OFF", TextRequest("l?\r"),
                            TextReply(r"(0|1)", fields={"isOn": lambda text: text == "1"}))
        self.assertEqual(getOnOff.decode(b"1\r\n"), {"isOn": True})
        self.assertEqual(getOnOff.decode(b"0\r\n"), {"isOn": False})

    def testSutterMoveAndPosition(self):
        move = Command(
            "MOVE",
            BinaryRequest("<clllc", fields=("header", "x", "y", "z", "terminator"),
                          constants={"header": b"M", "terminator": b"\r"}),
            BinaryReply("<c", fields=("acknowledgement",)))
        self.assertEqual(move.encode(x=4000, y=5000, z=6000),
                         pack("<clllc", b"M", 4000, 5000, 6000, b"\r"))
        self.assertEqual(move.decode(b"\r"), {"acknowledgement": b"\r"})

        position = Command(
            "GET_POSITION",
            BinaryRequest("<cc", fields=("header", "terminator"),
                          constants={"header": b"C", "terminator": b"\r"}),
            BinaryReply("<lllx", fields=("x", "y", "z")))
        self.assertEqual(position.encode(), b"C\r")
        self.assertEqual(position.reply.readLength, 13)
        self.assertEqual(position.decode(pack("<lllc", 1, 2, 3, b"\r")),
                         {"x": 1, "y": 2, "z": 3})

    def testIntegraWavelengthBothWays(self):
        getWavelength = Command(
            "GETWAVELENGTH", TextRequest("*GWL"),
            TextReply(r"PWC\s*:\s*(.+?)\r\n", fields={"wavelength": float}))
        self.assertEqual(getWavelength.encode(), b"*GWL")
        self.assertEqual(getWavelength.decode(b"PWC : 532.0\r\n"), {"wavelength": 532.0})

        setWavelength = Command("SETWAVELENGTH",
                                 TextRequest("*PWC{wavelength:05d}"))
        self.assertEqual(setWavelength.encode(wavelength=1064), b"*PWC01064")

    def testIntellidriveRegisters(self):
        setRegister = Command("SET_REGISTER",
                               TextRequest("s r{register} {value}\r"), TextReply("ok"))
        self.assertEqual(setRegister.encode(register="0x24", value=31), b"s r0x24 31\r")
        self.assertEqual(setRegister.decode(b"ok\r"), {})

        getRegister = Command("GET_REGISTER", TextRequest("g r{register}\n"),
                               TextReply(r"v\s(-?\d+)", fields={"value": int}))
        self.assertEqual(getRegister.encode(register="0xc9"), b"g r0xc9\n")
        self.assertEqual(getRegister.decode(b"v -1234\r"), {"value": -1234})

    def testTheSR830SnapReplyThatHasNoDescriptionToday(self):
        # SNAP? returns several comma-separated floats at one instant; the current
        # Command cannot say that at all, so SR830Device parses it by hand.
        snap = Command("SNAP", TextRequest("SNAP? 1,2,3,4\n"),
                        TextReply(r"([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+)",
                                  fields={"x": float, "y": float,
                                          "magnitude": float, "phase": float}))
        self.assertEqual(snap.encode(), b"SNAP? 1,2,3,4\n")
        self.assertEqual(snap.decode(b"1.0e-3,-2.0e-3,2.236e-3,-63.4\r\n"),
                         {"x": 0.001, "y": -0.002, "magnitude": 0.002236, "phase": -63.4})


COBOLT = """
{
  "device": "Cobolt laser",
  "commands": {
    "GET_POWER": {
      "request": {"template": "pa?\\r"},
      "reply":   {"pattern": "(\\\\d+\\\\.\\\\d+)", "fields": {"power": "float"}}
    },
    "SET_POWER": {
      "request": {"template": "p {power:0.3f}\\r"},
      "reply":   {"pattern": "OK"}
    },
    "GET_ON_OFF": {
      "request": {"template": "l?\\r"},
      "reply":   {"pattern": "(0|1)", "fields": {"isOn": "boolean01"}}
    },
    "TURN_ON": {
      "request": {"template": "l1\\r"},
      "reply":   {"pattern": "OK"}
    }
  }
}
"""

SUTTER = """
{
  "device": "Sutter MP-285",
  "commands": {
    "MOVE": {
      "request": {"format": "<clllc",
                  "fields": ["header", "x", "y", "z", "terminator"],
                  "constants": {"header": "M", "terminator": "\\r"}},
      "reply":   {"format": "<c", "fields": ["acknowledgement"]}
    },
    "GET_POSITION": {
      "request": {"format": "<cc", "fields": ["header", "terminator"],
                  "constants": {"header": "C", "terminator": "\\r"}},
      "reply":   {"format": "<lllx", "fields": ["x", "y", "z"]}
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
        byHand = Command("SET_POWER", TextRequest("p {power:0.3f}\r"), TextReply("OK"))
        self.assertEqual(fromFile.encode(power=0.05), byHand.encode(power=0.05))
        self.assertEqual(fromFile.decode(b"OK\r\n"), byHand.decode(b"OK\r\n"))

    def testABinaryCommandFromAFileBehavesLikeOneWrittenByHand(self):
        # The point of the whole layer: JSON adds notation, not behaviour.
        fromFile = self.sutter["MOVE"]
        byHand = Command(
            "MOVE",
            BinaryRequest("<clllc", fields=("header", "x", "y", "z", "terminator"),
                          constants={"header": b"M", "terminator": b"\r"}),
            BinaryReply("<c", fields=("acknowledgement",)))
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


class TestADescriptionThatDoesNotMakeSense(unittest.TestCase):
    def buildFrom(self, commands):
        return CommandDictionary.fromDescription({"device": "test", "commands": commands})

    def testACommandWithoutARequest(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"NOWHERE": {"reply": {"pattern": "OK"}}})
        self.assertIn("NOWHERE", str(raised.exception))

    def testARequestThatIsNeitherTextNorBinary(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"ODD": {"request": {"bytes": "M"}}})
        self.assertIn("template", str(raised.exception))
        self.assertIn("format", str(raised.exception))

    def testAConverterThatDoesNotExist(self):
        with self.assertRaises(BadDescription) as raised:
            self.buildFrom({"READ": {"request": {"template": "r?\r"},
                                     "reply": {"pattern": "(.+)", "fields": {"value": "decimal"}}}})
        message = str(raised.exception)
        self.assertIn("decimal", message)
        self.assertIn("float", message)      # names the ones that do exist

    def testTheByteOrderGuardStillFiresThroughTheFile(self):
        # A description is not a way around the checks the objects make.
        with self.assertRaises(ProtocolError) as raised:
            self.buildFrom({"MOVE": {"request": {"format": "clllc",
                                                 "fields": ["header", "x", "y", "z", "terminator"]}}})
        self.assertIn("<clllc", str(raised.exception))

    def testADescriptionWithNoCommandsAtAll(self):
        with self.assertRaises(BadDescription):
            CommandDictionary.fromDescription({"device": "test"})


if __name__ == "__main__":
    unittest.main()
