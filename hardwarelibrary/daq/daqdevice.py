from abc import ABC, abstractmethod
from enum import Enum


class DAQNotification(Enum):
    willAcquire    = "willAcquire"
    didAcquire     = "didAcquire"


class AnalogInputDevice(ABC):
    """Analog input capability (ADC). Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def getAnalogVoltage(self, channel):
        ...


class AnalogOutputDevice(ABC):
    """Analog output capability (DAC). Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def setAnalogVoltage(self, value, channel):
        ...


class AnalogIODevice(AnalogInputDevice, AnalogOutputDevice):
    """Both analog input and output.

    The configure and direction hooks are optional and default to no-ops.
    """

    def configureAnalogIO(self, parameters: dict):
        pass

    def getAnalogDirection(self, channel):
        pass

    def setAnalogDirection(self, channel):
        pass


class AnalogInputStreamDevice(AnalogInputDevice):
    """Hardware-timed analog input (waveform acquisition).

    Combine with PhysicalDevice in a driver. The driver implements the four
    streaming primitives; acquireWaveform is provided on top of them. scanRate is
    the per-channel sample rate in Hz; readStream returns one block of samples as
    {channel: [volts, ...]}.
    """

    @abstractmethod
    def configureStream(self, channels, scanRate):
        ...

    @abstractmethod
    def startStream(self):
        ...

    @abstractmethod
    def readStream(self):
        ...

    @abstractmethod
    def stopStream(self):
        ...

    def acquireWaveform(self, channels, scanRate, sampleCount):
        self.configureStream(channels, scanRate)
        samples = {channel: [] for channel in channels}
        self.startStream()
        try:
            while min(len(values) for values in samples.values()) < sampleCount:
                block = self.readStream()
                for channel in channels:
                    samples[channel].extend(block[channel])
        finally:
            self.stopStream()
        return {channel: values[:sampleCount] for channel, values in samples.items()}


class DigitalInputDevice(ABC):
    """Digital input capability. Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def getDigitalValue(self, channel):
        ...


class DigitalOutputDevice(ABC):
    """Digital output capability. Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def setDigitalValue(self, value, channel):
        ...


class DigitalIODevice(DigitalInputDevice, DigitalOutputDevice):
    """Both digital input and output.

    The configure and direction hooks are optional and default to no-ops.
    """

    def configureDigitalIO(self, parameters: dict):
        pass

    def getDigitalDirection(self, channel):
        pass

    def setDigitalDirection(self, channel):
        pass
