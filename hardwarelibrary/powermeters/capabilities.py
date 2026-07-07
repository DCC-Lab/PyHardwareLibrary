from abc import ABC, abstractmethod


class Capability(ABC):
    # Capability mixins are combined with a PhysicalDevice subclass, which sits
    # ahead of them in the MRO. PhysicalDevice is a cooperative base (it calls
    # super().__init__() after consuming the device-identity arguments), so a
    # mixin that holds per-instance state may define __init__ as long as it
    # takes no required arguments and forwards with super().__init__().
    pass


class WavelengthCalibratable(Capability):
    unit = "nm"
    isReadable = True
    isWritable = True

    def __init__(self):
        super().__init__()
        self.calibrationWavelength = None

    def getCalibrationWavelength(self):
        self.doGetCalibrationWavelength()
        return self.calibrationWavelength

    def setCalibrationWavelength(self, wavelength):
        self.doSetCalibrationWavelength(wavelength)
        self.doGetCalibrationWavelength()

    @abstractmethod
    def doGetCalibrationWavelength(self):
        ...

    @abstractmethod
    def doSetCalibrationWavelength(self, wavelength):
        ...


class AutoScalable(Capability):
    # The meter picks its measurement range automatically when auto-scaling is
    # on; turning it off pins the range to whatever scale is active. A meter may
    # also expose ScaleAdjustable to choose that range by hand.
    def autoScaleIsOn(self) -> bool:
        return self.doGetAutoScale()

    def turnAutoScaleOn(self):
        self.doTurnAutoScaleOn()

    def turnAutoScaleOff(self):
        self.doTurnAutoScaleOff()

    @abstractmethod
    def doGetAutoScale(self) -> bool:
        ...

    @abstractmethod
    def doTurnAutoScaleOn(self):
        ...

    @abstractmethod
    def doTurnAutoScaleOff(self):
        ...


class ScaleAdjustable(Capability):
    # The full-scale measurement range (e.g. 200e-3 W). Independent of
    # AutoScalable: setting a scale by hand generally requires auto-scaling off.
    unit = "W"
    isReadable = True
    isWritable = True

    def __init__(self):
        super().__init__()
        self.scale = None

    def getScale(self):
        self.doGetScale()
        return self.scale

    def setScale(self, scale):
        self.doSetScale(scale)
        self.doGetScale()

    def availableScales(self) -> list:
        return self.doGetAvailableScales()

    @abstractmethod
    def doGetScale(self):
        ...

    @abstractmethod
    def doSetScale(self, scale):
        ...

    @abstractmethod
    def doGetAvailableScales(self) -> list:
        ...
