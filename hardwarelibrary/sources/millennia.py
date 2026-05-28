from ..physicaldevice import PhysicalDevice
from ..communication.serialport import SerialPort
from .lasersourcedevice import LaserSourceDevice
from .capabilities import OnOffControl, ShutterControl, PowerControl


class MillenniaDevice(LaserSourceDevice, OnOffControl, ShutterControl, PowerControl):
    """Spectra-Physics Millennia eV CW DPSS pump laser (532 nm).

    Transport is the eV's back-panel USB port, which exposes a virtual COM port
    to the host (USB-CDC or an internal FTDI/CP210x bridge depending on the
    revision). From pyserial's point of view it is a serial port at 115200
    8-N-1, so the driver works whether the wire is native USB or, on older eV
    revisions, true RS-232 through an external USB-serial adapter. The driver
    is instantiated by portPath (e.g. /dev/cu.usbmodem* on macOS) like the
    CoboltDevice, because the unit's USB VID/PID has not been recorded here for
    discovery.

    The eV speaks a compact ASCII protocol. Action commands (ON, OFF, SHT:1,
    SHT:0) are executed silently with no reply, while queries (?D, ?SHT) return
    a single value line terminated by <CR><LF>. Because actions return nothing,
    queryString flushes the input first to drop any stray bytes left behind by
    a previous action or by power-up chatter (the approach the savikhin-lab eV
    driver relies on).

    ON/OFF gate the pump diodes; the shutter is a separate electromechanical
    block in front of the output, so the laser can be on with the shutter
    closed. doGetOnOffState therefore reads the diode emission state (?D), not
    the shutter. This eV dialect is not the classic Millennia Pro/V one
    (SHUTTER:x, ?STB); see manuals/Spectra-Physics-Millennia-eV-Serial-Commands.md.
    """

    defaultBaudRate = 115200
    commandTerminator = "\r"  # the eV accepts <CR>, <LF>, or both
    minPower = 0.05  # documented eV/Pro-s lower bound
    maxPower = 25.0  # eV25s spec; override on subclass for eV5/10/15/20

    def __init__(self, portPath=None, serialNumber=None, idProduct=None, idVendor=None):
        super().__init__(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.portPath = portPath
        self.port = None
        self.idn = None
        self.manufacturer = None
        self.model = None
        self.firmwareVersion = None
        self.laserSerialNumber = None

    def doInitializeDevice(self):
        try:
            self.port = SerialPort(portPath=self.portPath)
            self.port.open(baudRate=self.defaultBaudRate)
            self.readIdentity()
        except Exception:
            if self.port is not None and self.port.isOpen:
                self.port.close()
            raise PhysicalDevice.UnableToInitialize()

    def readIdentity(self):
        # The ?IDN reply is comma-separated: manufacturer, model, then a tail
        # whose ordering of firmware version and serial number is firmware-
        # dependent across the Millennia family. Keep the raw string and do a
        # best-effort parse into the positions seen on the lab unit's firmware
        # (SW214-00.004.096 on an eV25s); callers that care about precise
        # provenance should fall back to self.idn.
        self.idn = self.queryString("?IDN")
        fields = [field.strip() for field in self.idn.split(",")]
        self.manufacturer = fields[0] if len(fields) > 0 else None
        self.model = fields[1] if len(fields) > 1 else None
        self.firmwareVersion = fields[2] if len(fields) > 2 else None
        self.laserSerialNumber = fields[3] if len(fields) > 3 else None

    def doShutdownDevice(self):
        if self.port is not None:
            self.port.close()
            self.port = None

    def writeCommand(self, command):
        self.port.writeString(command + self.commandTerminator)

    def queryString(self, query) -> str:
        with self.port.transactionLock:
            self.port.flush()
            self.port.writeString(query + self.commandTerminator)
            return self.port.readString().strip()

    # OnOffControl hooks (the pump diodes)

    def doTurnOn(self):
        self.writeCommand("ON")

    def doTurnOff(self):
        self.writeCommand("OFF")

    def doGetOnOffState(self) -> bool:
        return self.queryString("?D") == "1"

    # ShutterControl hooks (the output-blocking shutter)

    def doOpenShutter(self):
        self.writeCommand("SHT:1")

    def doCloseShutter(self):
        self.writeCommand("SHT:0")

    def doGetShutterState(self) -> bool:
        return self.queryString("?SHT") == "1"

    # PowerControl hooks (output power in watts)

    def doSetPower(self, power: float):
        # The eV silently ignores out-of-range P: values, which would mask the
        # error downstream; refuse the call here so it fails loudly.
        if not (self.minPower <= power <= self.maxPower):
            raise ValueError(
                "power {0} W outside Millennia range [{1}, {2}] W".format(
                    power, self.minPower, self.maxPower))
        self.writeCommand("P:{0:.2f}".format(power))

    def doGetPower(self) -> float:
        # ?P returns either a bare number ("4.90") or a number with the W unit
        # ("4.90 W") depending on firmware; take the first whitespace-separated
        # token.
        return float(self.queryString("?P").split()[0])


class DebugMillenniaDevice(MillenniaDevice):
    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF2

    def __init__(self, serialNumber="debug"):
        super().__init__(portPath="debug", serialNumber=serialNumber)
        self.diodeIsOn = False
        self.shutterIsOpen = False
        self.outputPower = 0.0  # last-commanded output power in watts

    def doInitializeDevice(self):
        self.readIdentity()

    def doShutdownDevice(self):
        pass

    def writeCommand(self, command):
        if command == "ON":
            self.diodeIsOn = True
        elif command == "OFF":
            self.diodeIsOn = False
        elif command == "SHT:1":
            self.shutterIsOpen = True
        elif command == "SHT:0":
            self.shutterIsOpen = False
        elif command.startswith("P:"):
            self.outputPower = float(command[len("P:"):])

    def queryString(self, query) -> str:
        if query == "?D":
            return "1" if self.diodeIsOn else "0"
        elif query == "?SHT":
            return "1" if self.shutterIsOpen else "0"
        elif query == "?P":
            return "{0:.2f}".format(self.outputPower)
        elif query == "?IDN":
            # Mirrors the lab's eV25s ship report (firmware SW214-00.004.096,
            # laser-head S/N 3239) so readIdentity exercises real values.
            return "Spectra Physics, Millennia eV 25S, SW214-00.004.096, 3239"
        return "0"
