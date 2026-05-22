from abc import abstractmethod

from hardwarelibrary.physicaldevice import PhysicalDevice


class LaserSourceDevice(PhysicalDevice):
    def isLaserOn(self):
        return self.doGetOnOffState()

    def turnOn(self):
        self.doTurnOn()

    def turnOff(self):
        self.doTurnOff()

    def setPower(self, power: float):
        self.doSetPower(power)

    def power(self) -> float:
        return self.doGetPower()

    def interlock(self) -> bool:
        return self.doGetInterlockState()

    # Hardware hooks a driver must implement, on top of doInitializeDevice
    # and doShutdownDevice inherited from PhysicalDevice.
    @abstractmethod
    def doTurnOn(self):
        ...

    @abstractmethod
    def doTurnOff(self):
        ...

    @abstractmethod
    def doSetPower(self, power: float):
        ...

    @abstractmethod
    def doGetPower(self) -> float:
        ...

    @abstractmethod
    def doGetOnOffState(self) -> bool:
        ...

    @abstractmethod
    def doGetInterlockState(self) -> bool:
        ...
