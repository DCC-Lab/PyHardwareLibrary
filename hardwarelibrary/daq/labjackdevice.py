from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState, PhysicalDeviceNotification
from hardwarelibrary.daq import AnalogIODevice, DigitalIODevice, AnalogInputStreamDevice
import inspect


class LabjackDevice(PhysicalDevice, AnalogIODevice, DigitalIODevice, AnalogInputStreamDevice):
    """LabJack U3 (LV and HV). Use self.dev for features beyond the wrapped methods.

    The DAC outputs are slow: they are PWM-based (a ~732 Hz PWM signal smoothed by a
    2nd-order ~16 Hz low-pass filter, ~10 ms time constant), so setAnalogVoltage
    takes tens of ms to settle to its final value. Analog input, by contrast, can be
    streamed at hardware-timed rates (up to ~50 kHz aggregate) via acquireWaveform.
    """

    classIdVendor = 0x0cd5
    classIdProduct = 0x003

    def __init__(self, serialNumber="*", idProduct=0x003, idVendor=0x0cd5):
        super().__init__(serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.dev = None
        self._streamChannels = []
        self._streamData = None

    def doInitializeDevice(self):
        """Open the first U3 found, or the one matching serialNumber.

        PhysicalDevice normalizes a "*" or None serialNumber to the regex ".*",
        so both spellings mean "first found"; any other value is an exact serial.
        """
        import u3
        self.dev = u3.U3(autoOpen=False)
        if self.serialNumber in ("*", ".*"):
            self.dev.open()
        else:
            self.dev.open(firstFound=False, serial=int(self.serialNumber))
        self.dev.configU3()
        self.dev.getCalibrationData()

    def doShutdownDevice(self):
        self.dev.close()

    @property
    def isHighVoltage(self):
        return hasattr(self.dev, 'deviceName') and self.dev.deviceName == 'U3-HV'

    def setConfiguration(self, parameters: dict):
        raise NotImplementedError(
            "You must use default parameters or call the U3's labjack.dev functions directly"
        )

    def configuration(self):
        return self.dev.configU3()

    def configureAnalogIO(self, parameters: dict):
        self._validateConfigIOParameters(parameters)
        self.dev.configIO(**parameters)

    def configureDigitalIO(self, parameters: dict):
        self._validateConfigIOParameters(parameters)
        self.dev.configIO(**parameters)

    @staticmethod
    def _validateConfigIOParameters(parameters):
        # configureAnalogIO and configureDigitalIO both forward to the U3's single
        # configIO command; validate keys against its actual signature so an
        # unexpected key fails clearly here instead of deep inside configIO.
        import u3
        valid = set(inspect.signature(u3.U3.configIO).parameters) - {'self'}
        unexpected = set(parameters) - valid
        if unexpected:
            raise ValueError(
                f"Unexpected configIO parameter(s) {sorted(unexpected)}; "
                f"valid keys are {sorted(valid)}"
            )

    def getAnalogVoltage(self, channel):
        """Returns volts."""
        return self.dev.getAIN(channel)

    def setAnalogVoltage(self, value, channel):
        """value in volts, on DAC0 (channel 0) or DAC1 (channel 1)."""
        # 5000/5002 are the U3 Modbus registers for DAC0/DAC1.
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

    def configureStream(self, channels, sampleRate=None, scanRate=None):
        # scanRate is a deprecated synonym for sampleRate, kept temporarily for
        # callers written against the old AnalogInputStreamDevice contract.
        if sampleRate is None:
            sampleRate = scanRate
        self._streamChannels = list(channels)
        self.dev.streamConfig(
            NumChannels=len(self._streamChannels),
            PChannels=self._streamChannels,
            NChannels=[31] * len(self._streamChannels),
            Resolution=3,
            ScanFrequency=sampleRate,
        )

    def startStream(self):
        self.dev.streamStart()
        self._streamData = self.dev.streamData(convert=True)

    def readStream(self):
        packet = next(self._streamData)
        if packet is None:
            return {channel: [] for channel in self._streamChannels}
        return {channel: packet[f'AIN{channel}'] for channel in self._streamChannels}

    def stopStream(self):
        self.dev.streamStop()
        self._streamData = None


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
        self._streamChannels = []

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
        self._validateConfigIOParameters(parameters)

    def configureDigitalIO(self, parameters: dict):
        self._validateConfigIOParameters(parameters)

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

    def configureStream(self, channels, sampleRate=None, scanRate=None):
        self._streamChannels = list(channels)

    def startStream(self):
        pass

    def readStream(self):
        blockSize = 25
        return {channel: [self._analogValues.get(channel, 0.0)] * blockSize
                for channel in self._streamChannels}

    def stopStream(self):
        pass
