from enum import Enum
from typing import Union, Optional, Protocol

class DAQNotification(Enum):
    willAcquire    = "willAcquire"
    didAcquire     = "didAcquire"

class AnalogIOProtocol(Protocol):
    def configureAnalogIO(self, parameters:dict):
        pass

    def getAnalogDirection(self, channel):
        pass

    def setAnalogDirection(self, channel):
        pass

    def getAnalogVoltage(self, channel):
        pass

    def setAnalogVoltage(self, value, channel):
        pass

class DigitalIOProtocol(Protocol):
    def configureDigitalIO(self, parameters:dict):
        pass

    def getDigitalDirection(self, channel):
        pass

    def setDigitalDirection(self, channel):
        pass

    def getDigitalValue(self, channel):
        pass

    def setDigitalValue(self, value, channel):
        pass

class CounterProtocol(Protocol):
    def configureCounters(self, parameters:dict):
        pass

    def getCounterValue(self, channel):
        pass

class TimerProtocol(Protocol):
    def configureTimers(self, parameters:dict):
        pass

    def getTimerValue(self, channel):
        pass

    def startTimer(self, channel):
        pass

    def stopTimer(self, channel):
        pass
