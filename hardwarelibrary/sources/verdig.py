"""VerdiGDevice: one laser-source driver for a Coherent HOPS supply, over an
interchangeable transport.

A HOPS ("High Output Power Supply") laser (Genesis heads, Verdi G/C) is not a
serial device: its FT2232 is driven as bit-banged I2C, and all control -- power
DAC, ADC, shutter/enable GPIO, and the head's identity/calibration EEPROM across
the umbilical -- hangs off that one I2C bus (see manuals/Coherent-HOPS-*). So a
driver must speak that bus, either through Coherent's CohrHOPS.dll or natively.

VerdiGDevice holds one HOPSInterface and delegates every capability hook to it:

  - HOPSNativeInterface (hopsnative.py): pure-Python pyftdi I2C, no DLL (macOS/Linux)
  - HOPSDLLInterface (hopsdll.py): Coherent's CohrHOPS.dll (Windows/Linux)

Selection: VerdiGDevice(interface="auto") tries native first, then the DLL; pass
"native"/"dll" to force one, or an interface instance directly. The debug device
uses an in-memory DebugHOPSInterface and needs neither hardware nor pyftdi/DLL.

The lab unit reports as a Genesis CX-Vis (head G532). InterlockControl is part of
the contract, but the native interface cannot decode faults yet, so on the native
transport interlock()/faults() raise HOPSInterface.NotSupported (to be fixed once
the ?FF decode is reverse-engineered).
"""

from abc import ABC, abstractmethod

from ..physicaldevice import PhysicalDevice
from .lasersourcedevice import LaserSourceDevice
from .capabilities import OnOffControl, ShutterControl, PowerControl, InterlockControl


class HOPSInterface(ABC):
    """Transport-agnostic contract VerdiGDevice drives. Implemented by
    HOPSDLLInterface and HOPSNativeInterface."""

    name = "interface"

    class Unavailable(Exception):
        """This transport cannot be opened on this host (no DLL, no pyftdi, no
        device). Used by VerdiGDevice's auto-selection to fall through."""

    class NotSupported(Exception):
        """This transport cannot perform the requested operation (e.g. native
        interlock/fault decode)."""

    @abstractmethod
    def open(self): ...

    @abstractmethod
    def close(self): ...

    @abstractmethod
    def identity(self) -> dict:
        """{model, headType, serialNumber, maxPower (or None)}."""

    @abstractmethod
    def getPower(self) -> float: ...

    @abstractmethod
    def powerSetpoint(self) -> float: ...

    @abstractmethod
    def setPower(self, power: float): ...

    @abstractmethod
    def emissionOn(self) -> bool: ...

    @abstractmethod
    def setEmission(self, on: bool): ...

    @abstractmethod
    def shutterOpen(self) -> bool: ...

    @abstractmethod
    def setShutter(self, isOpen: bool): ...

    @abstractmethod
    def remoteOn(self) -> bool: ...

    @abstractmethod
    def setRemote(self, on: bool): ...

    @abstractmethod
    def mainTemperature(self) -> float: ...

    def interlockOk(self) -> bool:
        raise HOPSInterface.NotSupported(
            "interlock state is not available on the {0} interface".format(self.name))

    def faults(self) -> list:
        raise HOPSInterface.NotSupported(
            "fault decode is not available on the {0} interface".format(self.name))

    def diagnostics(self) -> dict:
        return {}


class VerdiGDevice(LaserSourceDevice, OnOffControl, ShutterControl, PowerControl,
                   InterlockControl):
    """Coherent Verdi-G laser on a HOPS supply (the lab head reports as a Genesis
    CX-Vis, G532), driven through an interchangeable HOPSInterface -- native
    pyftdi I2C or CohrHOPS.dll. See the module docstring."""

    classIdVendor = 0x0403   # FTDI FT2232 the HOPS supply enumerates as
    classIdProduct = 0x6010

    def __init__(self, interface="auto", url=None, serialNumber=None,
                 idProduct=None, idVendor=None):
        super().__init__(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self._interfaceChoice = interface
        self.url = url
        self.interface = None
        self.laserModel = None
        self.headType = None
        self.headSerialNumber = None
        self.maxPower = None

    def _interfaceCandidates(self):
        choice = self._interfaceChoice
        if isinstance(choice, HOPSInterface):
            return [lambda: choice]
        serial = None if self.serialNumber in (None, ".*") else self.serialNumber

        def native():
            from .hopsnative import HOPSNativeInterface
            return HOPSNativeInterface(url=self.url, serialNumber=serial)

        def dll():
            from .hopsdll import HOPSDLLInterface
            return HOPSDLLInterface(serialNumber=serial)

        table = {"auto": [native, dll], "native": [native], "dll": [dll]}
        if choice not in table:
            raise PhysicalDevice.UnableToInitialize(
                "interface must be 'auto', 'native', 'dll', or a HOPSInterface")
        return table[choice]

    def doInitializeDevice(self):
        errors = []
        for makeInterface in self._interfaceCandidates():
            interface = makeInterface()
            try:
                interface.open()
            except HOPSInterface.Unavailable as error:
                errors.append("{0}: {1}".format(interface.name, error))
                continue
            self.interface = interface
            break
        if self.interface is None:
            raise PhysicalDevice.UnableToInitialize(
                "No HOPS interface could be opened. " + " | ".join(errors))
        try:
            identity = self.interface.identity()
            self.laserModel = identity.get("model")
            self.headType = identity.get("headType")
            self.headSerialNumber = identity.get("serialNumber")
            self.maxPower = identity.get("maxPower")
            self.interface.setRemote(True)
        except Exception as error:
            self.interface.close()
            self.interface = None
            raise PhysicalDevice.UnableToInitialize(error) from error

    def doShutdownDevice(self):
        if self.interface is not None:
            try:
                self.interface.setRemote(False)
            finally:
                self.interface.close()
            self.interface = None

    # OnOffControl (emission enable)
    def doTurnOn(self):
        self.interface.setEmission(True)

    def doTurnOff(self):
        self.interface.setEmission(False)

    def doGetOnOffState(self) -> bool:
        return self.interface.emissionOn()

    # ShutterControl
    def doOpenShutter(self):
        self.interface.setShutter(True)

    def doCloseShutter(self):
        self.interface.setShutter(False)

    def doGetShutterState(self) -> bool:
        return self.interface.shutterOpen()

    # PowerControl
    def doSetPower(self, power: float):
        upper = self.maxPower if self.maxPower is not None else float("inf")
        if not (0.0 <= power <= upper):
            raise ValueError("power {0} W outside [0, {1}] W".format(power, self.maxPower))
        self.interface.setPower(power)

    def doGetPower(self) -> float:
        return self.interface.getPower()

    # InterlockControl (native raises HOPSInterface.NotSupported, by design)
    def doGetInterlockState(self) -> bool:
        return self.interface.interlockOk()

    # Extra, non-capability helpers delegated to the interface
    def powerSetpoint(self) -> float:
        return self.interface.powerSetpoint()

    def mainTemperature(self) -> float:
        return self.interface.mainTemperature()

    def faults(self) -> list:
        return self.interface.faults()

    def diagnostics(self) -> dict:
        return self.interface.diagnostics()

    def remoteControlIsOn(self) -> bool:
        return self.interface.remoteOn()

    def doGetStatusUserInfo(self) -> dict:
        info = {
            "power": self.doGetPower(),
            "setpoint": self.powerSetpoint(),
            "isLaserOn": self.doGetOnOffState(),
            "isShutterOpen": self.doGetShutterState(),
            "remoteControl": self.remoteControlIsOn(),
            "mainTemperature": self.mainTemperature(),
        }
        try:
            info["interlockOk"] = self.doGetInterlockState()
            info["faults"] = self.faults()
        except HOPSInterface.NotSupported:
            info["interlockOk"] = None
            info["faults"] = None
        return info


class DebugHOPSInterface(HOPSInterface):
    """In-memory HOPS transport for tests -- needs neither pyftdi nor the DLL.
    Fully capable (implements interlock/faults) so VerdiGDevice's whole contract can
    be exercised. Seeded to the lab Genesis CX-Vis (G532)."""

    name = "debug"

    def __init__(self):
        self.emission = False
        self.shutter = False
        self.remote = False
        self.setpoint = 0.0
        self.tmain = 36.0
        self.activeFaults = []
        self.opened = False

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def identity(self) -> dict:
        return {"model": "Genesis CX-Vis", "headType": "G532",
                "serialNumber": "VH5359", "maxPower": 7.344}

    def getPower(self) -> float:
        return self.setpoint if (self.emission and self.shutter) else 0.0

    def powerSetpoint(self) -> float:
        return self.setpoint

    def setPower(self, power: float):
        self.setpoint = power

    def emissionOn(self) -> bool:
        return self.emission

    def setEmission(self, on: bool):
        self.emission = bool(on)

    def shutterOpen(self) -> bool:
        return self.shutter

    def setShutter(self, isOpen: bool):
        self.shutter = bool(isOpen)

    def remoteOn(self) -> bool:
        return self.remote

    def setRemote(self, on: bool):
        self.remote = bool(on)

    def mainTemperature(self) -> float:
        return self.tmain

    def interlockOk(self) -> bool:
        return not any(f in self.activeFaults for f in ("Interlock fault",))

    def faults(self) -> list:
        return list(self.activeFaults)

    def diagnostics(self) -> dict:
        return {"mainTemperature": self.tmain}


class DebugVerdiGDevice(VerdiGDevice):
    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF4

    def __init__(self, serialNumber="debug"):
        super().__init__(interface=DebugHOPSInterface(), serialNumber=serialNumber)
