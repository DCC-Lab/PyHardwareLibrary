"""A prototype protocol description, developed in isolation inside its test file.

Nothing here is imported by the library, and nothing here touches a port: this is
a sketch of how an instrument protocol could be *described*, so the design can be
judged before any driver depends on it.

The idea is sans-I/O, the principle behind h11 and wsproto: the protocol is a pure
transformation over bytes and never performs the transaction. A Request turns named
arguments into the bytes to write; a Reply turns the bytes read back into named
values; neither owns a port, and neither stores what happened. That is what
separates this from the current Command, which describes the protocol, builds the
bytes, performs the I/O, and then keeps the reply on itself -- on a class
attribute shared by every instance of a driver.

Consequences worth noticing while reading:

  - a description is immutable and shareable; the result of an transaction is a plain
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
import re
import string
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


class Transaction:
    """One request and the reply it expects, named for a driver to call by name.

    Called Transaction rather than Command because it describes the round trip
    and performs none of it: encode() gives the caller the bytes to write,
    decode() turns what came back into values, and the caller owns the port in
    between. The word is already the library's for that pairing -- it is what
    CommunicationPort.transactionLock guards, a write and its read kept together
    against other threads.
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


class TestTransaction(unittest.TestCase):
    def testCarriesARequestAndItsReply(self):
        transaction = Transaction("GET_POWER", TextRequest("pa?\r"),
                            TextReply(r"(\d+\.\d+)", fields={"power": float}))
        self.assertEqual(transaction.encode(), b"pa?\r")
        self.assertEqual(transaction.decode(b"0.250\r\n"), {"power": 0.25})
        self.assertTrue(transaction.expectsReply)

    def testATransactionMayExpectNothingBack(self):
        transaction = Transaction("SET_WAVELENGTH", TextRequest("*PWC{wavelength:05d}"))
        self.assertFalse(transaction.expectsReply)
        self.assertEqual(transaction.encode(wavelength=532), b"*PWC00532")
        with self.assertRaises(ProtocolError):
            transaction.decode(b"anything")

    def testTheDescriptionIsSharedButTheResultIsNot(self):
        # The point of the whole exercise: two callers of one description cannot
        # overwrite each other, because nothing is stored on it.
        transaction = Transaction("GET_POWER", TextRequest("pa?\r"),
                            TextReply(r"(\d+\.\d+)", fields={"power": float}))
        first = transaction.decode(b"0.100\r\n")
        second = transaction.decode(b"0.900\r\n")
        self.assertEqual(first, {"power": 0.1})
        self.assertEqual(second, {"power": 0.9})
        self.assertEqual(vars(transaction).keys(), {"name", "request", "reply"})


class TestItCanExpressTheProtocolsWeAlreadyHave(unittest.TestCase):
    """The real test of the design: say what the drivers in this repo actually speak."""

    def testCoboltSetAndReadPower(self):
        setPower = Transaction("SET_POWER", TextRequest("p {power:0.3f}\r"), TextReply("OK"))
        self.assertEqual(setPower.encode(power=0.05), b"p 0.050\r")
        self.assertEqual(setPower.decode(b"OK\r\n"), {})

        getPower = Transaction("GET_POWER", TextRequest("pa?\r"),
                            TextReply(r"(\d+\.\d+)", fields={"power": float}))
        self.assertEqual(getPower.encode(), b"pa?\r")
        self.assertEqual(getPower.decode(b"0.0499\r\n"), {"power": 0.0499})

    def testCoboltOnOffStateAsABoolean(self):
        getOnOff = Transaction("GET_ON_OFF", TextRequest("l?\r"),
                            TextReply(r"(0|1)", fields={"isOn": lambda text: text == "1"}))
        self.assertEqual(getOnOff.decode(b"1\r\n"), {"isOn": True})
        self.assertEqual(getOnOff.decode(b"0\r\n"), {"isOn": False})

    def testSutterMoveAndPosition(self):
        move = Transaction(
            "MOVE",
            BinaryRequest("<clllc", fields=("header", "x", "y", "z", "terminator"),
                          constants={"header": b"M", "terminator": b"\r"}),
            BinaryReply("<c", fields=("acknowledgement",)))
        self.assertEqual(move.encode(x=4000, y=5000, z=6000),
                         pack("<clllc", b"M", 4000, 5000, 6000, b"\r"))
        self.assertEqual(move.decode(b"\r"), {"acknowledgement": b"\r"})

        position = Transaction(
            "GET_POSITION",
            BinaryRequest("<cc", fields=("header", "terminator"),
                          constants={"header": b"C", "terminator": b"\r"}),
            BinaryReply("<lllx", fields=("x", "y", "z")))
        self.assertEqual(position.encode(), b"C\r")
        self.assertEqual(position.reply.readLength, 13)
        self.assertEqual(position.decode(pack("<lllc", 1, 2, 3, b"\r")),
                         {"x": 1, "y": 2, "z": 3})

    def testIntegraWavelengthBothWays(self):
        getWavelength = Transaction(
            "GETWAVELENGTH", TextRequest("*GWL"),
            TextReply(r"PWC\s*:\s*(.+?)\r\n", fields={"wavelength": float}))
        self.assertEqual(getWavelength.encode(), b"*GWL")
        self.assertEqual(getWavelength.decode(b"PWC : 532.0\r\n"), {"wavelength": 532.0})

        setWavelength = Transaction("SETWAVELENGTH",
                                 TextRequest("*PWC{wavelength:05d}"))
        self.assertEqual(setWavelength.encode(wavelength=1064), b"*PWC01064")

    def testIntellidriveRegisters(self):
        setRegister = Transaction("SET_REGISTER",
                               TextRequest("s r{register} {value}\r"), TextReply("ok"))
        self.assertEqual(setRegister.encode(register="0x24", value=31), b"s r0x24 31\r")
        self.assertEqual(setRegister.decode(b"ok\r"), {})

        getRegister = Transaction("GET_REGISTER", TextRequest("g r{register}\n"),
                               TextReply(r"v\s(-?\d+)", fields={"value": int}))
        self.assertEqual(getRegister.encode(register="0xc9"), b"g r0xc9\n")
        self.assertEqual(getRegister.decode(b"v -1234\r"), {"value": -1234})

    def testTheSR830SnapReplyThatHasNoDescriptionToday(self):
        # SNAP? returns several comma-separated floats at one instant; the current
        # Command cannot say that at all, so SR830Device parses it by hand.
        snap = Transaction("SNAP", TextRequest("SNAP? 1,2,3,4\n"),
                        TextReply(r"([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+),([-\d.eE+]+)",
                                  fields={"x": float, "y": float,
                                          "magnitude": float, "phase": float}))
        self.assertEqual(snap.encode(), b"SNAP? 1,2,3,4\n")
        self.assertEqual(snap.decode(b"1.0e-3,-2.0e-3,2.236e-3,-63.4\r\n"),
                         {"x": 0.001, "y": -0.002, "magnitude": 0.002236, "phase": -63.4})


if __name__ == "__main__":
    unittest.main()
