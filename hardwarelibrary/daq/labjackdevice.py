from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState, PhysicalDeviceNotification
from hardwarelibrary.daq import AnalogIOProtocol, DigitalIOProtocol
import u3

class LabjackDevice(PhysicalDevice, AnalogIOProtocol, DigitalIOProtocol):
    classIdVendor = 0x0cd5
    classIdProduct = 0x003
    def __init__(self, serialNumber="*"):
        super().__init__(serialNumber, idProduct=0x003, idVendor=0x0cd5)
        self.dev = None

    def doInitializeDevice(self):
        self.dev = u3.U3(autoOpen=False)
        self.dev.open()
        self.dev.configU3()

    def doShutdownDevice(self):
        self.dev.close()

    def setConfiguration(self, parameters:dict):
        raise NotImplementedError("You must use default parameters or call the U3's labjack.dev functions directly")

    def configuration(self):
        return self.dev.configU3()

    def getAnalogVoltage(self, channel):
        value = self.dev.getAIN(channel)
        return value

    def setAnalogVoltage(self, value, channel):
        # Writes the dac.
        if channel == 0:
            register = 5000
        elif channel == 1:
            register = 5002
        self.dev.writeRegister(register, value)

    def setDigitalValue(self, value, channel):
        self.dev.setDOState(channel, value)

    def getDigitalValue(self, channel):
        return self.dev.getDIState(channel) != 0
