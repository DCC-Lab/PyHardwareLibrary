from abc import ABC, abstractmethod


class Capability(ABC):
    pass


class OnOffControl(Capability):
    def isLaserOn(self) -> bool:
        return self.doGetOnOffState()

    def turnOn(self):
        self.doTurnOn()

    def turnOff(self):
        self.doTurnOff()

    # Advisory availability flag for callers/UIs; a driver overrides it when an
    # external condition (e.g. Cobolt autostart) forbids manual turn-on. The
    # driver's doTurnOn still enforces and raises if called while not allowed.
    def canTurnOn(self) -> bool:
        return True

    @abstractmethod
    def doTurnOn(self):
        ...

    @abstractmethod
    def doTurnOff(self):
        ...

    @abstractmethod
    def doGetOnOffState(self) -> bool:
        ...


class PowerControl(Capability):
    unit = "W"
    isReadable = True
    isWritable = True

    def setPower(self, power: float):
        return self.doSetPower(power)

    def power(self) -> float:
        return self.doGetPower()

    @abstractmethod
    def doSetPower(self, power: float):
        ...

    @abstractmethod
    def doGetPower(self) -> float:
        ...


class InterlockControl(Capability):
    isReadable = True
    isWritable = False

    def interlock(self) -> bool:
        return self.doGetInterlockState()

    @abstractmethod
    def doGetInterlockState(self) -> bool:
        ...


class AutostartControl(Capability):
    def autostartIsOn(self) -> bool:
        return self.doGetAutostart()

    def turnAutostartOn(self):
        self.doTurnAutostartOn()

    def turnAutostartOff(self):
        self.doTurnAutostartOff()

    @abstractmethod
    def doGetAutostart(self) -> bool:
        ...

    @abstractmethod
    def doTurnAutostartOn(self):
        ...

    @abstractmethod
    def doTurnAutostartOff(self):
        ...


class WavelengthControl(Capability):
    unit = "nm"
    isReadable = True
    isWritable = True

    def setWavelength(self, wavelength: float):
        return self.doSetWavelength(wavelength)

    def wavelength(self) -> float:
        return self.doGetWavelength()

    def wavelengthRange(self) -> tuple:
        return self.doGetWavelengthRange()

    @abstractmethod
    def doSetWavelength(self, wavelength: float):
        ...

    @abstractmethod
    def doGetWavelength(self) -> float:
        ...

    @abstractmethod
    def doGetWavelengthRange(self) -> tuple:
        ...
