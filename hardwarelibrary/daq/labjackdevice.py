from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState, PhysicalDeviceNotification
from hardwarelibrary.daq import AnalogIOProtocol, DigitalIOProtocol
import u3


class LabjackDevice(PhysicalDevice, AnalogIOProtocol, DigitalIOProtocol):
    """A PhysicalDevice wrapper for the LabJack U3 (LV and HV).

    Provides lifecycle management (initializeDevice/shutdownDevice) and
    convenience methods for common I/O operations. For advanced features
    (timers, counters, streaming, SPI, I2C), use self.dev directly —
    it is the underlying u3.U3 instance with the full LabJackPython API.
    """

    classIdVendor = 0x0cd5
    classIdProduct = 0x003

    def __init__(self, serialNumber="*", idProduct=0x003, idVendor=0x0cd5):
        super().__init__(serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.dev = None

    def doInitializeDevice(self):
        self.dev = u3.U3(autoOpen=False)
        if self.serialNumber == ".*":
            self.dev.open()
        else:
            self.dev.open(firstFound=False, serial=int(self.serialNumber))
        self.dev.configU3()
        self.dev.getCalibrationData()

    def doShutdownDevice(self):
        self.dev.close()

    @property
    def isHighVoltage(self):
        """True if this is a U3-HV (hardware version >= 2.0)."""
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
        """Return the internal temperature sensor reading in Kelvin."""
        return self.dev.getTemperature()

    def toggleLED(self):
        """Toggle the device status LED."""
        self.dev.toggleLED()


class DebugLabjackDevice(LabjackDevice):
    """A hardware-free LabJack device for testing.

    Stores analog and digital values in dicts. Writing to DAC0 or DAC1
    makes the value readable on the corresponding AIN channel (loopback).
    """

    classIdProduct = 0xFFFB
    classIdVendor = 0xFFFF

    def __init__(self, serialNumber='debug'):
        PhysicalDevice.__init__(
            self, serialNumber=serialNumber,
            idProduct=self.classIdProduct, idVendor=self.classIdVendor
        )
        self.dev = None
        self._analog_values = {}
        self._digital_values = {}
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
        return self._analog_values.get(channel, 0.0)

    def setAnalogVoltage(self, value, channel):
        if channel not in (0, 1):
            raise ValueError(f"DAC channel must be 0 or 1, got {channel}")
        self._analog_values[channel] = value

    def setDigitalValue(self, value, channel):
        self._digital_values[channel] = bool(value)

    def getDigitalValue(self, channel):
        return self._digital_values.get(channel, False)

    def getTemperature(self):
        return self._temperature

    def toggleLED(self):
        pass
