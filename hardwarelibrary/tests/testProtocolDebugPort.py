"""A debug port that needs no code of its own, only a protocol description."""

import env
import unittest
from struct import pack

from hardwarelibrary.communication.debugport import ProtocolDebugPort
from hardwarelibrary.communication.protocol import (
    CommandDictionary, RequestDidNotMatch,
)
from hardwarelibrary.motion.sutterdevice import SutterDevice
from hardwarelibrary.physicaldevice import PhysicalDevice


LAMP = {
    "device": "A lamp that answers in text",
    "commands": {
        "SET_POWER": {
            "request": {"template": "p {power:0.3f}\r", "regex": r"p ([0-9.]+)\r",
                        "fields": {"power": "float"}},
            "reply": {"regex": "OK", "template": "OK\r\n"},
        },
        "GET_POWER": {
            "request": {"template": "pa?\r", "regex": r"pa\?\r"},
            "reply": {"regex": r"(\d+\.\d+)", "template": "{power:0.3f}\r\n",
                      "fields": {"power": "float"}},
        },
        "TURN_OFF": {
            "request": {"template": "l0\r", "regex": r"l0\r"},
            "reply": {"regex": "OK", "template": "OK\r\n"},
            "sets": {"power": 0.0},
        },
    },
}


class DebugLampDevice(PhysicalDevice):
    """A device with nothing but a protocol, to exercise performTransaction."""

    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF1
    protocol = CommandDictionary.fromDescription(LAMP)

    def __init__(self):
        """Bind to nothing: this instrument only ever exists in a debug port."""
        super().__init__(serialNumber="debug", idVendor=self.classIdVendor,
                         idProduct=self.classIdProduct)

    def doInitializeDevice(self):
        """Stand the instrument up out of its own description."""
        self.port = ProtocolDebugPort(self.protocol)
        self.port.open()

    def doShutdownDevice(self):
        """Put it away."""
        self.port.close()
        self.port = None


class TestPerformTransactionBelongsToEveryDevice(unittest.TestCase):
    """A driver that sets protocol needs no send-and-receive code of its own."""

    def setUp(self):
        self.device = DebugLampDevice()
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()

    def testALineIsReadToItsTerminatorAndAFrameByItsLength(self):
        # The reply says which: a text reply has no readLength, so the port reads
        # up to its own terminator instead. Nothing in the driver chooses.
        self.assertIsNone(self.device.protocol["GET_POWER"].reply.readLength)
        self.assertEqual(self.device.performTransaction("SET_POWER", power=0.25), {})
        self.assertEqual(self.device.performTransaction("GET_POWER"), {"power": 0.25})

    def testADeviceWithNoProtocolSaysSoBeforeTouchingThePort(self):
        # Never initialized, so its port is None: reaching the port at all would
        # raise an AttributeError instead of saying what is actually wrong.
        speechless = DebugLampDevice()
        speechless.protocol = None
        self.assertIsNone(speechless.port)
        with self.assertRaises(NotImplementedError) as raised:
            speechless.performTransaction("GET_POWER")
        self.assertIn("DebugLampDevice", str(raised.exception))


class TestItStandsInForTheSutter(unittest.TestCase):
    """The binary case, against the description SutterDevice itself speaks."""

    def setUp(self):
        self.port = ProtocolDebugPort(SutterDevice.protocol)
        self.port.open()

    def tearDown(self):
        self.port.close()

    def ask(self, name: str, **arguments) -> dict:
        """Send one command the way the driver does, and read its reply."""
        command = SutterDevice.protocol[name]
        self.port.writeData(command.encode(**arguments))
        return command.decode(self.port.readData(command.reply.readLength))

    def testItAnswersFromNothingButTheDescription(self):
        # No subclass, no process_command, no table of prefixes: the port was
        # handed a dictionary and that is all it has.
        self.assertEqual(type(self.port), ProtocolDebugPort)
        self.assertEqual(self.ask("GET_POSITION"), {"x": 0, "y": 0, "z": 0})

    def testWhatARequestCarriesIsWhatALaterReplyGivesBack(self):
        self.assertEqual(self.ask("MOVE", x=4000, y=5000, z=6000), {})
        self.assertEqual(self.ask("GET_POSITION"), {"x": 4000, "y": 5000, "z": 6000})

    def testACommandThatCarriesNothingCanStillChangeTheInstrument(self):
        # HOME is the case no description of bytes can reach: it takes no
        # arguments and moves the stage anyway. Its "sets" clause says so.
        self.ask("MOVE", x=1, y=2, z=3)
        self.assertEqual(self.ask("HOME"), {})
        self.assertEqual(self.ask("GET_POSITION"), {"x": 0, "y": 0, "z": 0})

    def testACommandWithNoSetsClauseLeavesTheInstrumentAlone(self):
        self.ask("MOVE", x=1, y=2, z=3)
        self.ask("WORK")
        self.assertEqual(self.ask("GET_POSITION"), {"x": 1, "y": 2, "z": 3})

    def testAnUnrecognizedRequestIsRefusedRatherThanIgnored(self):
        # A debug port that dropped it would hide the driver bug it exists to find.
        with self.assertRaises(RequestDidNotMatch):
            self.port.writeData(pack("<cc", b"Z", b"\r"))

    def testTheAcknowledgementIsTheOneTheDescriptionFixed(self):
        self.port.writeData(SutterDevice.protocol["HOME"].encode())
        self.assertEqual(self.port.readData(length=1), b"\r")


class TestItStandsInForATextInstrument(unittest.TestCase):
    """The same port, the same rules, a protocol made of lines."""

    def setUp(self):
        self.protocol = CommandDictionary.fromDescription(LAMP)
        self.port = ProtocolDebugPort(self.protocol)
        self.port.open()

    def tearDown(self):
        self.port.close()

    def ask(self, name: str, **arguments) -> dict:
        """Send one command and read the line it answers with."""
        command = self.protocol[name]
        self.port.writeData(command.encode(**arguments))
        return command.decode(self.port.readString())

    def testWhatWasSetIsWhatIsRead(self):
        self.assertEqual(self.ask("SET_POWER", power=0.25), {})
        self.assertEqual(self.ask("GET_POWER"), {"power": 0.25})

    def testAValueNeverSetReadsAsZero(self):
        self.assertEqual(self.ask("GET_POWER"), {"power": 0.0})

    def testASetsClauseWorksTheSameWayOnText(self):
        self.ask("SET_POWER", power=0.25)
        self.assertEqual(self.ask("TURN_OFF"), {})
        self.assertEqual(self.ask("GET_POWER"), {"power": 0.0})


if __name__ == "__main__":
    unittest.main()
