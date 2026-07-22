from abc import ABC, abstractmethod


class Capability(ABC):
    pass


class OutletSwitchingControl(Capability):
    """Switch individual outlets on and off and read their state.

    Outlets are addressed by their physical label (1-based): the first
    switchable outlet is outlet 1. Some strips also carry an always-on outlet
    that is not switchable and is not counted here.
    """

    def turnOutletOn(self, outlet: int):
        self.doSetOutletState(outlet, True)

    def turnOutletOff(self, outlet: int):
        self.doSetOutletState(outlet, False)

    def setOutletState(self, outlet: int, isOn: bool):
        self.doSetOutletState(outlet, isOn)

    def isOutletOn(self, outlet: int) -> bool:
        return self.doGetOutletState(outlet)

    @property
    def outletCount(self) -> int:
        return self.doGetOutletCount()

    @abstractmethod
    def doSetOutletState(self, outlet: int, isOn: bool):
        ...

    @abstractmethod
    def doGetOutletState(self, outlet: int) -> bool:
        ...

    @abstractmethod
    def doGetOutletCount(self) -> int:
        ...


class DefaultOutletControl(Capability):
    """Set the power-on (boot) state of individual outlets.

    Distinct from OutletSwitchingControl: this configures the state each outlet
    powers up in after the strip loses and regains mains power, not its state
    right now.
    """

    def setOutletDefaultOn(self, outlet: int):
        self.doSetOutletDefaultState(outlet, True)

    def setOutletDefaultOff(self, outlet: int):
        self.doSetOutletDefaultState(outlet, False)

    def setOutletDefaultState(self, outlet: int, isOn: bool):
        self.doSetOutletDefaultState(outlet, isOn)

    @abstractmethod
    def doSetOutletDefaultState(self, outlet: int, isOn: bool):
        ...


class CurrentMeteringControl(Capability):
    """Measure the strip's total current draw and accumulated charge.

    Only metering-capable strips (e.g. the PowerUSB "Smart" model) implement
    this; a driver mixes it in only when the hardware supports it. Values are in
    SI units at this boundary: current in amperes, accumulated charge in
    ampere-hours.
    """

    unit = "A"
    isReadable = True
    isWritable = False

    def current(self) -> float:
        return self.doGetCurrent()

    def accumulatedCharge(self) -> float:
        return self.doGetAccumulatedCharge()

    def resetAccumulatedCharge(self):
        self.doResetAccumulatedCharge()

    @abstractmethod
    def doGetCurrent(self) -> float:
        ...

    @abstractmethod
    def doGetAccumulatedCharge(self) -> float:
        ...

    @abstractmethod
    def doResetAccumulatedCharge(self):
        ...
