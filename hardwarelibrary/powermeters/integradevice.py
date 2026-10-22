import time
from enum import Enum

from hardwarelibrary.capabilities import WavelengthCalibrationCapability
from hardwarelibrary.communication.debugport import ProtocolDebugPort
from hardwarelibrary.communication.protocol import CommandDictionary
from hardwarelibrary.communication.usbport import USBPort
from hardwarelibrary.powermeters.powermeterdevice import PowerMeterDevice
from notificationcenter import NotificationCenter, Notification


# The Integra answers every query with one line ending in \r\n, and acknowledges
# nothing: *PWC sets the wavelength and stays silent, which is why it describes a
# request and no reply.
#
# One command is not here. "*STS" answers with a run of lines until one matching
# ":100000000", and a reply of an unknown number of lines is the one shape this
# description cannot yet state. Nothing in the driver ever called it, so nothing
# is lost today; when multi-line replies exist, it goes back as
#     "STATUS": {"request": {"template": "*STS", "regex": r"\*STS"}, ...}
integraProtocol = {
    "device": "Gentec Integra",
    "commands": {
        "GETPOWER": {
            "request": {"template": "*CVU", "regex": r"\*CVU"},
            "reply": {"regex": r"(.+?)\r\n", "template": "{power}\r\n",
                      "fields": {"power": "float"}},
        },
        "VERSION": {
            "request": {"template": "*VER", "regex": r"\*VER"},
            "reply": {"regex": r"(.+?)\r\n", "template": "{version}\r\n",
                      "fields": {"version": "text"}},
        },
        "GETWAVELENGTH": {
            "request": {"template": "*GWL", "regex": r"\*GWL"},
            "reply": {"regex": r"PWC\s*:\s*(.+?)\r\n",
                      "template": "PWC : {wavelength}\r\n",
                      "fields": {"wavelength": "float"}},
        },
        "SETWAVELENGTH": {
            "request": {"template": "*PWC{wavelength:05d}", "regex": r"\*PWC(\d{5})",
                        "fields": {"wavelength": "integer"}},
        },
    },
}


class IntegraDevice(PowerMeterDevice, WavelengthCalibrationCapability):
    """A Gentec Integra power meter, over USB.

    Its protocol is the dictionary above and this class only moves values between
    that description and a port.
    """

    classIdProduct = 0x0300
    classIdVendor = 0x1ad5

    protocol = CommandDictionary.fromDescription(integraProtocol)

    def __init__(self, serialNumber: str = None, idProduct: int = 0x0300,
                 idVendor: int = 0x1ad5):
        """Bind to one meter, or to "debug" for a port built from the description.

        Args:
            serialNumber: the meter's serial number, or "debug"
            idProduct: USB product id
            idVendor: USB vendor id
        """
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""

    def doInitializeDevice(self):
        """Open the port and read the firmware version, which proves it answers."""
        if self.serialNumber == "debug":
            self.port = ProtocolDebugPort(self.protocol)
            self.port.open()
        else:
            self.port = USBPort(idVendor=self.idVendor, idProduct=self.idProduct,
                                interfaceNumber=0, defaultEndPoints=(1, 2))
            self.port.open()
        self.doGetVersion()

    def doShutdownDevice(self):
        """Close the port and forget it."""
        self.port.close()
        self.port = None

    def doGetAbsolutePower(self):
        """Read the power in watts and keep it on absolutePower."""
        self.absolutePower = self.performTransaction("GETPOWER")["power"]

    def doGetCalibrationWavelength(self):
        """Read the wavelength the meter is calibrated for, in nanometres."""
        self.calibrationWavelength = self.performTransaction(
            "GETWAVELENGTH")["wavelength"]

    def doSetCalibrationWavelength(self, wavelength):
        """Tell the meter which wavelength to correct for.

        Args:
            wavelength: the wavelength in nanometres, as a whole number since the
                command writes it in five digits
        """
        self.performTransaction("SETWAVELENGTH", wavelength=wavelength)
        time.sleep(0.05) # This is necessary, see testIntegraDevice

    def doGetVersion(self):
        """Read the firmware version and keep it on version."""
        self.version = self.performTransaction("VERSION")["version"]
