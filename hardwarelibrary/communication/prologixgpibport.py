from .serialport import SerialPort


class PrologixGPIBPort(SerialPort):
    """A GPIB instrument reached through a Prologix GPIB-USB controller.

    The Prologix controller enumerates as a generic FTDI serial port
    (VID 0x0403 / PID 0x6001), so this IS a SerialPort: it inherits the FTDI
    discovery and every read/write primitive unchanged, and adds only the
    controller handshake in open(). GPIB payloads are ordinary ASCII, so callers
    use the inherited readString/writeString (and the writeStringReadMatch
    family); there is no GPIB-specific read/write method.

    The controller runs in manual-read mode (++auto 0): a query is read back by
    an explicit '++read eoi', which this class issues inside readString(). So the
    driver still talks to the port with plain writeString/readString (and the
    writeStringReadMatch family) and never touches a GPIB-specific method. Manual
    read is used rather than ++auto 1 because auto mode addresses the instrument
    to talk after every command, including commands with no reply (e.g. SENS),
    which leaves the bus in an error state.
    """

    def __init__(self, gpibAddress, portPath=None, idVendor=0x0403,
                 idProduct=0x6001, serialNumber=None):
        super().__init__(idVendor=idVendor, idProduct=idProduct,
                         serialNumber=serialNumber, portPath=portPath)
        self.gpibAddress = gpibAddress

    def open(self, baudRate=115200, timeout=1.0):
        super().open(baudRate=baudRate, timeout=timeout)
        self.configureController()

    def configureController(self):
        """Send the one-time Prologix controller handshake.

        ++eos 2 appends a line-feed to commands forwarded to the instrument (the
        SR830 and most GPIB instruments accept LF or EOI as a terminator).
        ++eot_enable 0 keeps the controller from appending its own terminator to
        replies: the instrument already ends its response with CR-LF, so a second
        appended LF would be left stranded in the buffer and corrupt the next
        read.
        """
        for command in ("++mode 1",
                        "++addr {0}".format(self.gpibAddress),
                        "++auto 0",
                        "++eoi 1",
                        "++eos 2",
                        "++eot_enable 0",
                        "++read_tmo_ms 1500"):
            self.writeString(command + "\n")

    def readString(self, endPoint=None) -> str:
        # Manual-read mode: ask the controller to read the addressed instrument's
        # reply (until EOI), then read the forwarded bytes with the inherited
        # serial readString. Keeping this here lets the driver use the ordinary
        # readString/writeStringReadMatch primitives unchanged.
        self.writeString("++read eoi\n")
        return super().readString(endPoint)
