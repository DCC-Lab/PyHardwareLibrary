import time
from enum import Enum
from hardwarelibrary.communication import USBPort, TextCommand, MultilineTextCommand
from hardwarelibrary.powermeters.powermeterdevice import PowerMeterDevice
from hardwarelibrary.capabilities import WavelengthCalibrationCapability
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class IntegraDevice(PowerMeterDevice, WavelengthCalibrationCapability):
    classIdProduct = 0x0300
    classIdVendor = 0x1ad5
    commands = {
        "GETPOWER":      TextCommand(name="GETPOWER",      requestEncoder="*CVU", replyDecoder=r"(.+?)\r\n"),
        "VERSION":       TextCommand(name="VERSION",       requestEncoder="*VER", replyDecoder=r"(.+?)\r\n"),
        "STATUS":        MultilineTextCommand(name="STATUS", requestEncoder="*STS", replyDecoder=r"(.+?)\r\n", lastLinePattern=":100000000"),
        "GETWAVELENGTH": TextCommand(name="GETWAVELENGTH", requestEncoder="*GWL", replyDecoder=r"PWC\s*:\s*(.+?)\r\n"),
        "SETWAVELENGTH": TextCommand(name="SETWAVELENGTH", requestEncoder="*PWC{0:05d}"),
    }

    def __init__(self, serialNumber:str = None, idProduct:int = 0x0300, idVendor:int = 0x1ad5):
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""

    def doInitializeDevice(self):
        self.port = USBPort(idVendor=self.idVendor, idProduct=self.idProduct, interfaceNumber=0, defaultEndPoints=(1, 2))
        self.port.open()
        self.doGetVersion()

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def doGetAbsolutePower(self):
        getPowerCommand = IntegraDevice.commands["GETPOWER"]
        getPowerCommand.send(port=self.port)
        self.absolutePower = float(getPowerCommand.matchGroups[0])

    def doGetCalibrationWavelength(self):
        getWavelength = IntegraDevice.commands["GETWAVELENGTH"]
        getWavelength.send(port=self.port)
        self.calibrationWavelength = float(getWavelength.matchGroups[0])

    def doSetCalibrationWavelength(self, wavelength):
        setWavelength = IntegraDevice.commands["SETWAVELENGTH"]
        setWavelength.send(port=self.port, params=(wavelength))
        time.sleep(0.05) # This is necessary, see testIntegraDevice

    def doGetVersion(self):
        getVersion = IntegraDevice.commands["VERSION"]
        getVersion.send(port=self.port)
        self.version = getVersion.matchGroups[0]

