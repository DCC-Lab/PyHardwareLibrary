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
