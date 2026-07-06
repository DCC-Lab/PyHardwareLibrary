import re
import time

from hardwarelibrary.communication import SerialPort
from hardwarelibrary.communication.communicationport import (
    CommunicationReadTimeout, CommunicationReadNoMatch,
)
from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.powermeters.powermeterdevice import PowerMeterDevice

FLOAT_PATTERN = r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"


class FieldMasterDevice(PowerMeterDevice):
    """Coherent FieldMaster GS laser power/energy meter over RS-232.

    The meter has no USB identity of its own: it connects through a generic
    FTDI RS-232 adaptor, so classIdVendor/classIdProduct are the FTDI values
    (0x0403/0x6001) shared by every FTDI cable. When several FTDI adaptors are
    present, disambiguate with the adaptor's serialNumber (e.g. "FTFDLOTS") or
    by passing an explicit portPath.

    Protocol (hardwarelibrary/manuals/Coherent_FieldMaster_GS_Manual, IEEE-488.2 style):
      9600 baud, no parity, 8 data bits, 1 stop bit, no handshaking (3-wire,
      only TxD/RxD/GND wired). 'pw?' returns watts in scientific notation,
      e.g. '1.430000e-03'.

    The message terminator is a front-panel Menu setting on the meter: LF
    ('\\n'), CR ('\\r'), or both/CR-LF ('\\r\\n'). The `terminator` argument
    (default LF) is only the first guess: doInitializeDevice probes with it and,
    if the meter does not answer, tries the remaining combinations until one
    replies, so a mismatched Menu setting self-heals. The working value is left
    on the port's `terminator`, which both readString and the command writes
    use, keeping reads and writes in sync with the meter.

    Important operational constraint from the manual: the FieldMaster GS only
    answers RS-232 while it is on its Home or Trend screen. On any other screen
    it silently buffers commands. When no terminator elicits a reply,
    doInitializeDevice raises with that hint.
    """

    candidateTerminators = (b'\n', b'\r', b'\r\n')

    classIdVendor = 0x0403
    classIdProduct = 0x6001

    def __init__(self, serialNumber: str = None, idProduct: int = 0x6001,
                 idVendor: int = 0x0403, portPath: str = None,
                 terminator: bytes = b'\n'):
        super().__init__(serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.portPath = portPath
        self.terminator = terminator
        self.version = ""

    def doInitializeDevice(self):
        if self.portPath is not None:
            self.port = SerialPort(portPath=self.portPath)
        else:
            self.port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct,
                                   serialNumber=self.serialNumber)
            if self.port.portPath is None:
                raise PhysicalDevice.UnableToInitialize("No FieldMaster (FTDI adaptor) connected")

        self.port.open(baudRate=9600, timeout=1.0)

        if not self.detectTerminator():
            self.port.close()
            self.port = None
            raise PhysicalDevice.UnableToInitialize(
                "FieldMaster is connected but not answering on any terminator "
                "(LF/CR/CR-LF). Put it on its HOME screen (front panel): it "
                "ignores RS-232 from any other screen."
            )

        self.doGetVersion()

    def detectTerminator(self):
        """Set port.terminator to the meter's Menu terminator by probing.

        The terminator is a front-panel Menu setting (LF/CR/CR-LF), so a query
        only draws a reply when the terminator matches. The configured
        self.terminator is tried first, then the remaining candidates. On the
        first probe that answers, the working value is kept on the port and on
        self.terminator and True is returned; False means none replied.
        """
        ordered = [self.terminator]
        ordered += [term for term in self.candidateTerminators if term != self.terminator]
        for term in ordered:
            self.clearMeterLineBuffer()
            self.port.terminator = term
            try:
                self.doGetAbsolutePower()
            except (CommunicationReadTimeout, CommunicationReadNoMatch):
                continue
            self.terminator = term
            return True
        return False

    def clearMeterLineBuffer(self):
        """Complete and drain any partial command a previous probe left in the
        meter's input buffer so it cannot corrupt the next probe."""
        self.port.writeData(b"\r\n")
        time.sleep(0.2)
        self.port.flush()

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def sendQuery(self, command, replyPattern=FLOAT_PATTERN, maxLines=3):
        """Send a query and return the first capture group matching replyPattern.

        The meter answers a query with a single value line, but a stray echo or
        blank line can precede it, so up to maxLines are read before giving up.
        """
        self.port.flush()
        self.port.writeString(command + self.port.terminator.decode())
        for _ in range(maxLines):
            reply = self.port.readString()
            match = re.search(replyPattern, reply)
            if match is not None:
                return match.groups()[0]
        raise CommunicationReadNoMatch(
            "No reply matching '{0}' from FieldMaster for '{1}'".format(replyPattern, command)
        )

    def doGetAbsolutePower(self):
        self.absolutePower = float(self.sendQuery("pw?"))

    def doGetCalibrationWavelength(self):
        wavelengthInMeters = float(self.sendQuery("wv?"))
        self.calibrationWavelength = wavelengthInMeters * 1e9

    def doSetCalibrationWavelength(self, wavelength):
        """Set the calibration wavelength. wavelength is in nanometres; the
        meter's 'wv' command takes metres, so it is converted on the wire."""
        wavelengthInMeters = wavelength * 1e-9
        self.port.flush()
        self.port.writeString("wv {0:.6e}".format(wavelengthInMeters) + self.port.terminator.decode())

    def getEnergy(self):
        """Return the current energy reading in joules ('en?')."""
        return float(self.sendQuery("en?"))

    def doGetVersion(self):
        self.version = self.sendQuery("v", replyPattern=r"(.+)")


class DebugFieldMasterDevice(FieldMasterDevice):
    """Hardware-free FieldMaster GS for tests. Holds power and calibration
    state in memory; power tracks a fixed simulated reading."""

    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF1

    def __init__(self, serialNumber='debug'):
        PhysicalDevice.__init__(self, serialNumber=serialNumber,
                                idProduct=self.classIdProduct, idVendor=self.classIdVendor)
        self.portPath = None
        self.terminator = b'\n'
        self.version = "Debug FieldMaster GS 1.0"
        self._simulatedPower = 1.43e-3
        self._calibrationWavelengthInNanometers = 1064.0

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass

    def doGetAbsolutePower(self):
        self.absolutePower = self._simulatedPower

    def doGetCalibrationWavelength(self):
        self.calibrationWavelength = self._calibrationWavelengthInNanometers

    def doSetCalibrationWavelength(self, wavelength):
        self._calibrationWavelengthInNanometers = wavelength

    def getEnergy(self):
        return self._simulatedPower

    def doGetVersion(self):
        pass
