from hardwarelibrary.communication.debugport import ProtocolDebugPort
from hardwarelibrary.communication.protocol import CommandDictionary
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.motion.linearmotiondevice import Direction, LinearMotionDevice
from hardwarelibrary.physicaldevice import PhysicalDevice


# The whole protocol of the MP-285, as data. Every frame is binary and
# fixed-size: a header byte, the values, a carriage return. Naming the header and
# the terminator as constants rather than padding them over is what lets the same
# description serve both directions -- a constant is written on the way out and
# required on the way in, so a ProtocolDebugPort recognises a request by the very
# bytes the driver sends, and the driver is told when an acknowledgement is not
# the b"\r" it expected.

sutterProtocol = {
    "device": "Sutter MP-285",
    "commands": {
        "MOVE": {
            "request": {"struct": "<clllc",
                        "fields": ["header", "x", "y", "z", "terminator"],
                        "constants": {"header": "M", "terminator": "\r"}},
            "reply": {"struct": "<c", "fields": ["acknowledgement"],
                      "constants": {"acknowledgement": "\r"}},
        },
        "GET_POSITION": {
            "request": {"struct": "<cc", "fields": ["header", "terminator"],
                        "constants": {"header": "C", "terminator": "\r"}},
            "reply": {"struct": "<lllc", "fields": ["x", "y", "z", "terminator"],
                      "constants": {"terminator": "\r"}},
        },
        "HOME": {
            "request": {"struct": "<cc", "fields": ["header", "terminator"],
                        "constants": {"header": "H", "terminator": "\r"}},
            "reply": {"struct": "<c", "fields": ["acknowledgement"],
                      "constants": {"acknowledgement": "\r"}},
        },
        "WORK": {
            "request": {"struct": "<cc", "fields": ["header", "terminator"],
                        "constants": {"header": "Y", "terminator": "\r"}},
            "reply": {"struct": "<c", "fields": ["acknowledgement"],
                      "constants": {"acknowledgement": "\r"}},
        },
    },
}


class SutterDevice(LinearMotionDevice):
    """A Sutter Instruments MP-285 translation stage, in native microsteps.

    The protocol is described once, in sutterProtocol above, and this class only
    moves bytes between that description and a port. Nothing here builds a frame
    by hand, and nothing here checks an acknowledgement by hand either: the
    description says the answer to MOVE, HOME and WORK is a carriage return, so a
    stage that answers anything else raises before this class sees it.
    """

    classIdVendor = 4930
    classIdProduct = 1

    protocol = CommandDictionary.fromDescription(sutterProtocol)

    def __init__(self, serialNumber: str = None):
        """Prepare a stage, without opening anything yet.

        Args:
            serialNumber: the serial number of the stage to match, or "debug" to
                talk to a ProtocolDebugPort instead of hardware. None takes
                any Sutter that is connected.
        """
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor,
                         idProduct=self.classIdProduct)
        self.port = None
        self.nativeStepsPerMicrons = 16

        # All values are in native units (i.e. microsteps)
        self.xMinLimit = 0
        self.yMinLimit = 0
        self.zMinLimit = 0
        self.xMaxLimit = 25000*16
        self.yMaxLimit = 25000*16
        self.zMaxLimit = 25000*16

    def __del__(self):
        """Close the port if it is still open, and say nothing if it is not."""
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def doInitializeDevice(self):
        """Open the port and confirm the stage answers.

        Raises:
            PhysicalDevice.UnableToInitialize: when no stage matches, when the
                port cannot be opened, or when the first command goes unanswered.
                The port is closed again before the exception leaves.
        """
        try:
            if self.serialNumber == "debug":
                self.port = self.DebugSerialPort(self.protocol)
                self.port.open()
            else:
                portPath = SerialPort.matchAnyPort(idVendor=self.idVendor,
                                                   idProduct=self.idProduct,
                                                   serialNumber=self.serialNumber)
                if portPath is None:
                    raise PhysicalDevice.UnableToInitialize("No Sutter Device connected")

                self.port = SerialPort(portPath=portPath, delay=0.1)
                self.port.open(baudRate=128000, timeout=10)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize(
                    "Cannot allocate port for serial '{0}'".format(self.serialNumber))

            self.performTransaction("GET_POSITION")

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDevice.UnableToInitialize(error)

    def doShutdownDevice(self):
        """Close the port and forget it."""
        self.port.close()
        self.port = None

    def positionInMicrosteps(self) -> (int, int, int):
        """The position in microsteps. Kept for compatibility with doGetPosition."""
        return self.doGetPosition()

    def doGetPosition(self) -> (int, int, int):
        """Ask the stage where it is.

        Returns:
            The (x, y, z) position in microsteps.
        """
        position = self.performTransaction("GET_POSITION")
        return (position["x"], position["y"], position["z"])

    def doMoveTo(self, position):
        """Move to an absolute position.

        Args:
            position: an (x, y, z) triplet in microsteps, rounded to whole steps
                since the frame packs them as longs
        """
        x, y, z = position
        self.performTransaction("MOVE", x=int(x), y=int(y), z=int(z))

    def doMoveBy(self, displacement):
        """Move by a relative displacement, reading the position first.

        Two transactions, held under one lock: a relative move is a read, an
        addition and a write, and a stage that another caller moved in between
        would be displaced from a position that is no longer where it is.

        Args:
            displacement: a (dx, dy, dz) triplet in microsteps

        Raises:
            Exception: when the position cannot be read, since there is then
                nothing to add the displacement to.
        """
        dx, dy, dz = displacement
        with self.port.transactionLock:
            x, y, z = self.doGetPosition()
            if x is None:
                raise Exception("Unable to read position from device")
            self.doMoveTo((x+dx, y+dy, z+dz))

    def doHome(self):
        """Send the stage to its home position."""
        self.performTransaction("HOME")

    def work(self):
        """Send the stage home, then to its work position."""
        self.home()
        self.performTransaction("WORK")

    class DebugSerialPort(ProtocolDebugPort):
        """An MP-285 without an MP-285, out of its own description.

        The description carries the whole protocol, so the only thing left here is
        the one fact its bytes cannot state: HOME carries no arguments and still
        sends the stage to the origin.
        """

        def answerFor(self, command) -> dict:
            """Move to the origin on HOME, then answer as the description says.

            Args:
                command: the command that was recognized

            Returns:
                The values its reply carries, taken from what is remembered.
            """
            if command.name == "HOME":
                self.values.update(x=0, y=0, z=0)
            return super().answerFor(command)
