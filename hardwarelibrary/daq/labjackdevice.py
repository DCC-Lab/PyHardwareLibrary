from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState, PhysicalDeviceNotification
from hardwarelibrary.daq import AnalogIODevice, DigitalIODevice
import u3


class LabjackDevice(PhysicalDevice, AnalogIODevice, DigitalIODevice):
    """LabJack U3 (LV and HV). Use self.dev for features beyond the wrapped methods."""

    classIdVendor = 0x0cd5
    classIdProduct = 0x003

    def __init__(self, serialNumber="*", idProduct=0x003, idVendor=0x0cd5):
        super().__init__(serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.dev = None

    def doInitializeDevice(self):
        self.dev = u3.U3(autoOpen=False)
        if self.serialNumber == "*":
            self.dev.open()
        else:
            self.dev.open(firstFound=False, serial=int(self.serialNumber))
        self.dev.configU3()
        self.dev.getCalibrationData()

    def doShutdownDevice(self):
        self.dev.close()

    @property
    def isHighVoltage(self):
        return hasattr(self.dev, 'hardwareVersion') and self.dev.hardwareVersion >= 2.0

    def setConfiguration(self, parameters: dict):
        raise NotImplementedError(
            "You must use default parameters or call the U3's labjack.dev functions directly"
        )

    def configuration(self):
        return self.dev.configU3()

    def configureAnalogIO(self, parameters: dict):
        self.dev.configIO(**parameters)

    def configureDigitalIO(self, parameters: dict):
        self.dev.configIO(**parameters)

    def getAnalogVoltage(self, channel):
        return self.dev.getAIN(channel)

    def setAnalogVoltage(self, value, channel):
        if channel == 0:
            register = 5000
        elif channel == 1:
            register = 5002
        else:
            raise ValueError(f"DAC channel must be 0 or 1, got {channel}")
        self.dev.writeRegister(register, value)

    def setDigitalValue(self, value, channel):
        self.dev.setDOState(channel, value)

    def getDigitalValue(self, channel):
        return self.dev.getDIState(channel) != 0

    def getTemperature(self):
        """Returns Kelvin."""
        return self.dev.getTemperature()

    def toggleLED(self):
        self.dev.toggleLED()


class DebugLabjackDevice(LabjackDevice):
    """Hardware-free U3 for tests. DAC channels 0,1 loop back to AIN 0,1."""

    classIdProduct = 0xFFFB
    classIdVendor = 0xFFFF

    def __init__(self, serialNumber='debug'):
        PhysicalDevice.__init__(
            self, serialNumber=serialNumber,
            idProduct=self.classIdProduct, idVendor=self.classIdVendor
        )
        self.dev = None
        self._analogValues = {}
        self._digitalValues = {}
        self._temperature = 298.0

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass

    @property
    def isHighVoltage(self):
        return False

    def setConfiguration(self, parameters: dict):
        raise NotImplementedError(
            "You must use default parameters or call the U3's labjack.dev functions directly"
        )

    def configuration(self):
        return {'DeviceName': 'DebugU3', 'SerialNumber': 0}

    def configureAnalogIO(self, parameters: dict):
        pass

    def configureDigitalIO(self, parameters: dict):
        pass

    def getAnalogVoltage(self, channel):
        return self._analogValues.get(channel, 0.0)

    def setAnalogVoltage(self, value, channel):
        if channel not in (0, 1):
            raise ValueError(f"DAC channel must be 0 or 1, got {channel}")
        self._analogValues[channel] = value

    def setDigitalValue(self, value, channel):
        self._digitalValues[channel] = bool(value)

    def getDigitalValue(self, channel):
        return self._digitalValues.get(channel, False)

    def getTemperature(self):
        return self._temperature

    def toggleLED(self):
        pass
