"""Capability mixins shared by every device family.

A capability is a feature an instrument may have (turn on/off, open a shutter,
read a voltage, ...). A driver declares the capabilities it supports by mixing
them alongside a PhysicalDevice subclass. Every public method here is concrete and
delegates to a do* hook the driver implements: getXxx() calls doGetXxx(), and the
hook is the abstract one, so the public method stays free to validate arguments and
post notifications on every driver's behalf. A hook a driver may leave alone (an
optional feature, or a default built on the other hooks) is not abstract, but it
still carries the do prefix. Mixins carry the *Capability suffix; only instantiable
hardware drivers are named *Device.

PhysicalDevice.capabilities() / hasCapability() introspect these by walking the
MRO for Capability subclasses, so every capability across every family must
subclass the single Capability base defined here.
"""

import inspect
from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum


class Capability(ABC):
    # Capability mixins are combined with a PhysicalDevice subclass, which sits
    # ahead of them in the MRO. PhysicalDevice is a cooperative base (it calls
    # super().__init__() after consuming the device-identity arguments), so a
    # mixin that holds per-instance state may define __init__ as long as it
    # takes no required arguments and forwards with super().__init__().
    pass


# ---------------------------------------------------------------------------
# Laser source capabilities
# ---------------------------------------------------------------------------

class OnOffCapability(Capability):
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


class ShutterCapability(Capability):
    # Distinct from OnOffCapability: the shutter is a mechanical block in front of
    # the output, so it can be opened or closed while the laser stays on.
    def isShutterOpen(self) -> bool:
        return self.doGetShutterState()

    def openShutter(self):
        self.doOpenShutter()

    def closeShutter(self):
        self.doCloseShutter()

    @abstractmethod
    def doOpenShutter(self):
        ...

    @abstractmethod
    def doCloseShutter(self):
        ...

    @abstractmethod
    def doGetShutterState(self) -> bool:
        ...


class PowerCapability(Capability):
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


class InterlockCapability(Capability):
    isReadable = True
    isWritable = False

    def interlock(self) -> bool:
        return self.doGetInterlockState()

    @abstractmethod
    def doGetInterlockState(self) -> bool:
        ...


class AutostartCapability(Capability):
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


class WavelengthCapability(Capability):
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


class DispersionCapability(Capability):
    unit = "fs^2"  # group delay dispersion (GDD)
    isReadable = True
    isWritable = True

    def setDispersion(self, dispersion: float):
        return self.doSetDispersion(dispersion)

    def dispersion(self) -> float:
        return self.doGetDispersion()

    def dispersionRange(self) -> tuple:
        return self.doGetDispersionRange()

    @abstractmethod
    def doSetDispersion(self, dispersion: float):
        ...

    @abstractmethod
    def doGetDispersion(self) -> float:
        ...

    @abstractmethod
    def doGetDispersionRange(self) -> tuple:
        ...


# ---------------------------------------------------------------------------
# Power meter capabilities
# ---------------------------------------------------------------------------

class WavelengthCalibrationCapability(Capability):
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


class AutoScaleCapability(Capability):
    # The meter picks its measurement range automatically when auto-scaling is
    # on; turning it off pins the range to whatever scale is active. A meter may
    # also expose ScaleCapability to choose that range by hand.
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


class ScaleCapability(Capability):
    # The full-scale measurement range (e.g. 200e-3 W). Independent of
    # AutoScaleCapability: setting a scale by hand generally requires auto-scaling
    # off.
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


# ---------------------------------------------------------------------------
# DAQ capabilities
# ---------------------------------------------------------------------------

class AnalogInputCapability(Capability):
    """Analog input capability (ADC). Combine with PhysicalDevice in a driver."""

    def getAnalogVoltage(self, channel):
        """Returns the voltage measured on channel, in volts."""
        return self.doGetAnalogVoltage(channel)

    @abstractmethod
    def doGetAnalogVoltage(self, channel):
        ...


class AnalogOutputCapability(Capability):
    """Analog output capability (DAC). Combine with PhysicalDevice in a driver."""

    def setAnalogVoltage(self, value, channel):
        """Set the output on channel to value, in volts."""
        return self.doSetAnalogVoltage(value, channel)

    @abstractmethod
    def doSetAnalogVoltage(self, value, channel):
        ...


class AnalogIOCapability(AnalogInputCapability, AnalogOutputCapability):
    """Both analog input and output.

    The configure and direction hooks are optional and default to no-ops.
    """

    def configureAnalogIO(self, parameters: dict):
        """Apply the driver-specific analog configuration in parameters."""
        return self.doConfigureAnalogIO(parameters)

    def getAnalogDirection(self, channel):
        """Returns whether channel is configured as an input or an output."""
        return self.doGetAnalogDirection(channel)

    def setAnalogDirection(self, channel):
        """Configure the direction of channel."""
        return self.doSetAnalogDirection(channel)

    def doConfigureAnalogIO(self, parameters: dict):
        pass

    def doGetAnalogDirection(self, channel):
        pass

    def doSetAnalogDirection(self, channel):
        pass


class AnalogInputStreamCapability(AnalogInputCapability):
    """Hardware-timed analog input (waveform acquisition).

    Combine with PhysicalDevice in a driver. The driver implements the four
    streaming primitives; acquireWaveform is provided on top of them. sampleRate
    is the per-channel sample rate in Hz; readStream returns one block of samples
    as {channel: [volts, ...]}. The aggregate rate (sampleRate times the number
    of channels) is the hardware limit, not sampleRate alone.

    One-shot acquisition (blocks until sampleCount samples are collected):

        waveform = device.acquireWaveform(channels=[0], sampleRate=5000, sampleCount=1000)
        samples = waveform[0]   # 1000 calibrated voltages from AIN0

    Continuous acquisition with the primitives:

        device.configureStream(channels=[0, 1], sampleRate=2000)
        device.startStream()
        try:
            while acquiring:
                block = device.readStream()   # {0: [...], 1: [...]}
                process(block[0])
        finally:
            device.stopStream()
    """

    class Notification(Enum):
        willAcquire = "willAcquire"
        didAcquire  = "didAcquire"

    def configureStream(self, channels, sampleRate=None, **parameters):
        """Set up a hardware-timed acquisition of channels at sampleRate (Hz).

        Any further keyword argument is passed on to the driver, which is where
        instrument-specific options live (the SR830 takes a sampleClock, for
        instance). A driver that ignores sampleRate, because its clock is
        external, accepts None for it.
        """
        return self.doConfigureStream(channels, sampleRate, **parameters)

    def startStream(self):
        """Start the configured acquisition."""
        return self.doStartStream()

    def readStream(self):
        """Returns the samples acquired since the last read, as {channel: [volts, ...]}."""
        return self.doReadStream()

    def stopStream(self):
        """Stop the acquisition and release any hardware streaming resources."""
        return self.doStopStream()

    def acquireWaveform(self, channels, sampleRate, sampleCount):
        """Acquire exactly sampleCount samples per channel, blocking until done.

        Returns {channel: [volts, ...]} truncated to sampleCount per channel.
        """
        return self.doAcquireWaveform(channels, sampleRate, sampleCount)

    @abstractmethod
    def doConfigureStream(self, channels, sampleRate):
        ...

    @abstractmethod
    def doStartStream(self):
        ...

    @abstractmethod
    def doReadStream(self):
        ...

    @abstractmethod
    def doStopStream(self):
        ...

    def doAcquireWaveform(self, channels, sampleRate, sampleCount):
        """Configure, start, and drain the stream, then stop it.

        Optional: a driver whose hardware has a native one-shot acquisition
        overrides this instead of being drained a block at a time.
        """
        self.configureStream(channels, sampleRate)
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


class InputSource(Enum):
    """Signal input a lock-in demodulator measures, named instrument-agnostically.

    A driver maps each member to its hardware setting (for the SR830: SingleEnded
    -> input A, Differential -> A-B, Current1M -> current input at 1 MOhm,
    Current100M -> current input at 100 MOhm).
    """

    SingleEnded  = "SingleEnded"
    Differential = "Differential"
    Current1M    = "Current1M"
    Current100M  = "Current100M"


class PhaseLockedDetectionCapability(Capability):
    """Phase-locked (lock-in) detection capability. Combine with PhysicalDevice.

    Reads the demodulated outputs (X, Y, R, theta) and reference frequency, and
    configures the signal input source, sensitivity (full-scale, in volts), and
    time constant (in seconds). Sensitivity and time constant are expressed in
    physical units so no instrument's discrete step encoding leaks into the
    contract; a driver snaps a requested value to its nearest supported step.
    """

    def getInPhaseVoltage(self):
        """Returns the in-phase component X, in volts."""
        return self.doGetInPhaseVoltage()

    def getQuadratureVoltage(self):
        """Returns the quadrature component Y, in volts."""
        return self.doGetQuadratureVoltage()

    def getMagnitude(self):
        """Returns the magnitude R = sqrt(X^2 + Y^2), in volts."""
        return self.doGetMagnitude()

    def getPhase(self):
        """Returns the phase theta, in degrees."""
        return self.doGetPhase()

    def getReferenceFrequency(self):
        """Returns the reference frequency, in Hz."""
        return self.doGetReferenceFrequency()

    def getInputSource(self) -> InputSource:
        """Returns the signal input the demodulator currently measures."""
        return self.doGetInputSource()

    def setInputSource(self, source: InputSource):
        """Select which signal input (an InputSource member) the demodulator measures."""
        return self.doSetInputSource(source)

    def getSensitivity(self):
        """Returns the full-scale sensitivity, in volts."""
        return self.doGetSensitivity()

    def setSensitivity(self, volts):
        """Set the full-scale sensitivity to the nearest supported step, in volts."""
        return self.doSetSensitivity(volts)

    def getTimeConstant(self):
        """Returns the time constant, in seconds."""
        return self.doGetTimeConstant()

    def setTimeConstant(self, seconds):
        """Set the time constant to the nearest supported step, in seconds."""
        return self.doSetTimeConstant(seconds)

    def supportedInputSources(self):
        """Returns the InputSource members this instrument supports, or None."""
        return self.doGetSupportedInputSources()

    def supportedSensitivities(self):
        """Returns the full-scale sensitivities (volts) this instrument supports, or None."""
        return self.doGetSupportedSensitivities()

    def supportedTimeConstants(self):
        """Returns the time constants (seconds) this instrument supports, or None."""
        return self.doGetSupportedTimeConstants()

    def getDemodulatedValues(self):
        """One reading of all demodulated outputs plus the reference frequency."""
        return self.doGetDemodulatedValues()

    @abstractmethod
    def doGetInPhaseVoltage(self):
        ...

    @abstractmethod
    def doGetQuadratureVoltage(self):
        ...

    @abstractmethod
    def doGetMagnitude(self):
        ...

    @abstractmethod
    def doGetPhase(self):
        ...

    @abstractmethod
    def doGetReferenceFrequency(self):
        ...

    @abstractmethod
    def doGetInputSource(self) -> InputSource:
        ...

    @abstractmethod
    def doSetInputSource(self, source: InputSource):
        ...

    @abstractmethod
    def doGetSensitivity(self):
        ...

    @abstractmethod
    def doSetSensitivity(self, volts):
        ...

    @abstractmethod
    def doGetTimeConstant(self):
        ...

    @abstractmethod
    def doSetTimeConstant(self, seconds):
        ...

    def doGetSupportedInputSources(self):
        """Optional: None means the instrument does not advertise a list."""
        return None

    def doGetSupportedSensitivities(self):
        """Optional: None means the instrument does not advertise a list."""
        return None

    def doGetSupportedTimeConstants(self):
        """Optional: None means the instrument does not advertise a list."""
        return None

    def doGetDemodulatedValues(self):
        """Read the outputs one at a time.

        Optional: a driver overrides this when the hardware can read them
        atomically, at a single coherent timepoint.
        """
        return {
            "X": self.getInPhaseVoltage(),
            "Y": self.getQuadratureVoltage(),
            "R": self.getMagnitude(),
            "theta": self.getPhase(),
            "referenceFrequency": self.getReferenceFrequency(),
        }


class TriggerSource(Enum):
    """Where a triggerable acquisition gets its start.

    A trigger starts (arms) an acquisition; it is not the sampling clock (see
    SampleClock), which is a separate concept.
    """

    Internal = "Internal"   # start immediately
    External = "External"   # start on an external hardware trigger


class SampleClock(Enum):
    """What paces the samples of a stream acquisition: the device's own timebase
    at a fixed rate (Internal), or one sample per external clock/trigger edge
    (External). Distinct from TriggerSource, which only starts the acquisition."""

    Internal = "Internal"
    External = "External"


class TriggerCapability(Capability):
    """Capability for a device whose acquisition can be armed to a trigger.

    setTriggerSource selects an internal (immediate) start versus waiting for an
    external hardware trigger, and softwareTrigger() issues a manual trigger edge
    (equivalent to a pulse on the external trigger line). Combine with
    PhysicalDevice in a driver.
    """

    def setTriggerSource(self, source: 'TriggerSource'):
        """Select whether the acquisition starts immediately or on an external trigger."""
        return self.doSetTriggerSource(source)

    def getTriggerSource(self) -> 'TriggerSource':
        """Returns the currently selected TriggerSource."""
        return self.doGetTriggerSource()

    def softwareTrigger(self):
        """Issue a manual (software) trigger edge."""
        return self.doSoftwareTrigger()

    def supportedTriggerSources(self):
        """Returns the TriggerSource members this device supports, or None."""
        return self.doGetSupportedTriggerSources()

    @abstractmethod
    def doSetTriggerSource(self, source: 'TriggerSource'):
        ...

    @abstractmethod
    def doGetTriggerSource(self) -> 'TriggerSource':
        ...

    @abstractmethod
    def doSoftwareTrigger(self):
        ...

    def doGetSupportedTriggerSources(self):
        """Optional: None means the device does not advertise a list."""
        return None


class DigitalInputCapability(Capability):
    """Digital input capability. Combine with PhysicalDevice in a driver."""

    def getDigitalValue(self, channel):
        """Returns the logic level read on channel."""
        return self.doGetDigitalValue(channel)

    @abstractmethod
    def doGetDigitalValue(self, channel):
        ...


class DigitalOutputCapability(Capability):
    """Digital output capability. Combine with PhysicalDevice in a driver."""

    def setDigitalValue(self, value, channel):
        """Drive channel to the logic level value."""
        return self.doSetDigitalValue(value, channel)

    @abstractmethod
    def doSetDigitalValue(self, value, channel):
        ...


class DigitalIOCapability(DigitalInputCapability, DigitalOutputCapability):
    """Both digital input and output.

    The configure and direction hooks are optional and default to no-ops.
    """

    def configureDigitalIO(self, parameters: dict):
        """Apply the driver-specific digital configuration in parameters."""
        return self.doConfigureDigitalIO(parameters)

    def getDigitalDirection(self, channel):
        """Returns whether channel is configured as an input or an output."""
        return self.doGetDigitalDirection(channel)

    def setDigitalDirection(self, channel):
        """Configure the direction of channel."""
        return self.doSetDigitalDirection(channel)

    def doConfigureDigitalIO(self, parameters: dict):
        pass

    def doGetDigitalDirection(self, channel):
        pass

    def doSetDigitalDirection(self, channel):
        pass


# ---------------------------------------------------------------------------
# Power strip capabilities
# ---------------------------------------------------------------------------


class OutletSwitchingCapability(Capability):
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


class DefaultOutletCapability(Capability):
    """Set the power-on (boot) state of individual outlets.

    Distinct from OutletSwitchingCapability: this configures the state each
    outlet powers up in after the strip loses and regains mains power, not its
    state right now.
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


class CurrentMeteringCapability(Capability):
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


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


def allCapabilities() -> list:
    """Return every capability mixin defined here, in declaration order.

    Use this to enumerate what the library can express, as opposed to
    PhysicalDevice.capabilities(), which reports what one device supports. The
    Capability marker base is excluded, and so are the drivers that mix these
    in: a driver is a Capability subclass too, but it is declared in its own
    module.
    """
    # A module's __dict__ is insertion-ordered, so filtering it in place yields
    # the classes in the order they are declared above, grouped by family.
    return [candidate for candidate in list(globals().values())
            if isinstance(candidate, type)
            and issubclass(candidate, Capability)
            and candidate is not Capability
            and candidate.__module__ == __name__]


CapabilityMember = namedtuple("CapabilityMember", ["name", "signature", "isAbstract"])


def capabilityInterface(aCapability) -> dict:
    """Describe what a capability declares, as three lists under the keys
    extends, publicAPI and hooks.

    The publicAPI entries are the methods a user calls; the hooks are the ones a
    driver implements. Both are CapabilityMember tuples, with an empty signature
    for a property. Members a parent capability declares are left to that parent,
    so a listing built from allCapabilities() never repeats them.
    """
    publicAPI, hooks = [], []
    for name, member in vars(aCapability).items():
        if name.startswith("_"):
            continue

        if isinstance(member, property):
            signature = ""
            isAbstract = getattr(member.fget, "__isabstractmethod__", False)
        elif inspect.isfunction(member):
            signature = inspect.signature(member)
            signature = str(signature.replace(
                parameters=list(signature.parameters.values())[1:]))
            isAbstract = getattr(member, "__isabstractmethod__", False)
        else:
            continue

        # The do prefix is what marks a hook, not abstractness: a hook that is
        # optional, or that defaults to a composition of the other hooks, is
        # concrete and would otherwise be mistaken for public API.
        destination = hooks if name.startswith("do") else publicAPI
        destination.append(CapabilityMember(name, signature, isAbstract))

    extends = [klass for klass in aCapability.__mro__[1:]
               if issubclass(klass, Capability) and klass is not Capability]
    return {"extends": extends, "publicAPI": publicAPI, "hooks": hooks}
