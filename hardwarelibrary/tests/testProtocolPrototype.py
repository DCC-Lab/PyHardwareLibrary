"""The protocol description of communication/protocol.py, exercised end to end.

These tests were written before the module existed, against a prototype living in
this file, so that the design could be judged before any driver depended on it.
The prototype has since moved to hardwarelibrary/communication/protocol.py and
SutterDevice speaks through it; what stays here is the whole of its behaviour --
both directions, the JSON layer, the refusals, and the protocols this repository
already speaks, said in the new terms.
"""

import env
import os
import tempfile
import unittest
from struct import calcsize, pack

from hardwarelibrary.communication.protocol import (
    BadDescription, BinaryFrame, Command, CommandDictionary, DidNotMatch, Frame,
    MissingArgument, ProtocolError, ReplyDidNotMatch, RequestDidNotMatch, TextFrame,
    booleanFromZeroOrOne, integerFromHexadecimal,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTextFrameWritingALine(unittest.TestCase):
    def assertReadsBackWhatItWrote(self, frame: TextFrame, **values):
        """The regex must match the line the template just produced.

        The two notations are written out separately and nothing holds them
        together but this. A template whose own regex does not match what it
        writes describes a line no debug port could ever recognise, and the
        driver would still work -- which is exactly how such a mistake survives
        until someone runs against a mock.
        """
        self.assertEqual(frame.decode(frame.encode(**values)), values)

    def testBuildsAConstantRequest(self):
        request = TextFrame("pa?\r", r"pa\?\r")
        self.assertEqual(request.encode(), b"pa?\r")
        self.assertReadsBackWhatItWrote(request)

    def testSubstitutesNamedArguments(self):
        request = TextFrame("p {power:0.3f}\r", r"p ([0-9.]+)\r",
                            fields={"power": float})
        self.assertEqual(request.encode(power=0.5), b"p 0.500\r")
        self.assertReadsBackWhatItWrote(request, power=0.5)

    def testWhateverEndsTheLineIsVisibleInTheTemplate(self):
        for template, regex, written in (
                ("*GWL", r"\*GWL", b"*GWL"),
                ("g r0xc9\n", "g r0xc9\n", b"g r0xc9\n"),
                ("SYST:ERR?\r\n", r"SYST:ERR\?\r\n", b"SYST:ERR?\r\n")):
            request = TextFrame(template, regex)
            self.assertEqual(request.encode(), written)
            self.assertReadsBackWhatItWrote(request)

    def testNamesTheArgumentsItNeeds(self):
        request = TextFrame("s r{register} {value}\r", r"s r(\S+) (-?\d+)\r",
                            fields={"register": str, "value": int})
        self.assertEqual(request.arguments, ("register", "value"))
        self.assertReadsBackWhatItWrote(request, register="0x24", value=31)

    def testAMissingArgumentSaysWhichOne(self):
        with self.assertRaises(MissingArgument) as raised:
            TextFrame("p {power:0.3f}\r", r"p ([0-9.]+)\r").encode()
        self.assertIn("power", str(raised.exception))


class TestBinaryFrameWritingAFrame(unittest.TestCase):
    def assertReadsBackWhatItWrote(self, frame: BinaryFrame, **values):
        """The frame must recognise what it just packed.

        Cheaper to satisfy than its text counterpart, since pack and unpack are
        each other's inverse over one format -- but not free: it is the constants
        that can be wrong here, and a frame whose own header it refuses is a
        frame no debug port would ever recognise.
        """
        self.assertEqual(frame.decode(frame.encode(**values)), values)

    def testPacksConstantsOnly(self):
        request = BinaryFrame("<cc", fields=("header", "terminator"),
                              constants={"header": b"C", "terminator": b"\r"})
        self.assertEqual(request.encode(), b"C\r")
        self.assertEqual(request.arguments, ())
        self.assertReadsBackWhatItWrote(request)

    def testPacksNamedValuesBetweenConstants(self):
        request = BinaryFrame(
            "<clllc", fields=("header", "x", "y", "z", "terminator"),
            constants={"header": b"M", "terminator": b"\r"})
        self.assertEqual(request.arguments, ("x", "y", "z"))
        self.assertEqual(request.encode(x=1, y=2, z=3),
                         pack("<clllc", b"M", 1, 2, 3, b"\r"))
        self.assertReadsBackWhatItWrote(request, x=1, y=2, z=3)

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
        self.assertEqual(vars(command).keys(),
                         {"name", "request", "reply", "specimen"})

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

    def testWhitespaceIsSkippedAsStructItselfSkipsIt(self):
        # struct allows spaces between codes, and a space taken for a code would
        # shift every name after it against its type.
        self.assertEqual(calcsize("<l l"), calcsize("<ll"))
        self.assertEqual(BinaryFrame.structCodes("<l l"), ("l", "l"))
        spaced = BinaryFrame("<c lll c", fields=("header", "x", "y", "z", "terminator"),
                             constants={"header": b"M", "terminator": b"\r"})
        self.assertEqual(spaced.parameters,
                         (("x", "int32"), ("y", "int32"), ("z", "int32")))


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


class TestADescriptionThatIsWrongAboutItself(unittest.TestCase):
    """What reading a file cannot catch, and speaking the protocol can."""

    def faultsOf(self, commands) -> list:
        return CommandDictionary.fromDescription(
            {"device": "test", "commands": commands}).faults()

    def testARealDescriptionHasNothingToSay(self):
        cobolt = CommandDictionary.fromJSON(COBOLT)
        self.assertEqual(cobolt.faults(), [])
        self.assertIs(cobolt.validate(), cobolt)
        self.assertEqual(CommandDictionary.fromJSON(SUTTER).faults(), [])

    def testATemplateAndARegexThatDescribeDifferentLines(self):
        # Everything counts out right; they simply are not the same line. Only
        # writing one and reading it back can tell.
        faults = self.faultsOf({"SET": {"request": {
            "template": "p {power:0.3f}\r", "regex": r"q ([0-9.]+)\r",
            "fields": {"power": "float"}}}})
        self.assertEqual(len(faults), 1)
        self.assertIn("SET request", faults[0])
        self.assertIn("cannot be written and read back", faults[0])

    def testATemplateAndFieldsThatDisagreeOnAName(self):
        faults = self.faultsOf({"SET": {"request": {
            "template": "p {power:0.3f}\r", "regex": r"p ([0-9.]+)\r",
            "fields": {"powr": "float"}}}})
        self.assertIn("the template writes power and the fields name powr",
                      "\n".join(faults))

    def testAnExpressionThatCapturesMoreThanIsNamed(self):
        faults = self.faultsOf({"GET": {
            "request": {"template": "v?\r", "regex": r"v\?\r"},
            "reply": {"regex": r"(\d+) (\d+)", "template": "{a} {b}\r\n",
                      "fields": {"a": "integer"}}}})
        self.assertIn("GET reply", faults[0])
        self.assertIn("captures 2 value(s) but 1 field(s) are named", faults[0])

    def testAStructThatPacksMoreThanItNames(self):
        faults = self.faultsOf({"MOVE": {"request": {
            "struct": "<clll", "fields": ["header", "x", "y"],
            "constants": {"header": "M"}}}})
        self.assertIn("packs 4 value(s) but 3 field(s) are named", faults[0])

    def testTwoCommandsWhereTheFirstAnswersForTheSecond(self):
        # The failure a debug port would show and a driver never would: READ_ALL
        # is loose enough to match READ_ONE's request, and comes first.
        faults = self.faultsOf({
            "READ_ALL": {"request": {"template": "r\r", "regex": "r"}},
            "READ_ONE": {"request": {"template": "r1\r", "regex": "r1"}},
        })
        self.assertEqual(len(faults), 1)
        self.assertIn("READ_ONE: its request is taken for READ_ALL", faults[0])

    def testATypeItCannotMakeASpecimenForIsSaidRatherThanSkipped(self):
        faults = self.faultsOf({"SEND": {"request": {
            "struct": "<4s", "fields": ["payload"]}}})
        self.assertIn("no specimen for payload, of type bytes", faults[0])

    def testACommandMayGiveTheSpecimenItsOwnExpressionAccepts(self):
        strict = {"request": {"template": "n {count:d}\r", "regex": r"n ([2-9])\r",
                              "fields": {"count": "integer"}}}
        self.assertEqual(len(self.faultsOf({"SET": strict})), 1)

        rescued = dict(strict, specimen={"count": 5})
        self.assertEqual(self.faultsOf({"SET": rescued}), [])

    def testValidateNamesTheDeviceAndEveryFaultAtOnce(self):
        described = CommandDictionary.fromDescription({"device": "a bad lamp", "commands": {
            "SET": {"request": {"template": "p {power:0.3f}\r",
                                "regex": r"q ([0-9.]+)\r",
                                "fields": {"power": "float"}}},
            "MOVE": {"request": {"struct": "<clll", "fields": ["header", "x", "y"],
                                 "constants": {"header": "M"}}},
        }})
        with self.assertRaises(BadDescription) as raised:
            described.validate()
        message = str(raised.exception)
        self.assertIn("a bad lamp is not consistent with itself", message)
        self.assertIn("SET request", message)
        self.assertIn("MOVE request", message)


if __name__ == "__main__":
    unittest.main()
