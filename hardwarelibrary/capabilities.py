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

Each capability names its notification enum in its `notification` attribute, and
every public method is wrapped in @notifies so an observer hears about the
operation without the driver writing a line for it. An operation that changes the
instrument posts will* before and did* after; a read posts only did*, because
bracketing a value that is merely being read doubles the traffic on the hot paths
(a voltage sampled in a loop) for no added information.

did* is posted whether the operation succeeded or not, so a will* is always
followed by its did*: the user_info carries "result" and "error", one of which is
None, and an observer decides what to do from the presence of an error. A hook that
raises still lets its exception through untouched, so a caller sees it as before.

Capabilities related by inheritance share one enum, so `notification` is the same
object on all of them and their members are interchangeable: AnalogInput,
AnalogOutput, AnalogIO and AnalogInputStream all post AnalogNotification, and the
digital trio posts DigitalNotification. Sharing is what makes an observer of
AnalogNotification.didSetAnalogVoltage hear the post whether the device mixed in
AnalogOutputCapability or the combined AnalogIOCapability -- members are keyed by
identity, so two same-named members of two enums would never cross-fire.

PhysicalDevice.capabilities() / hasCapability() introspect these by walking the
MRO for Capability subclasses, so every capability across every family must
subclass the single Capability base defined here.
"""

import functools
import inspect
from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum

from notificationcenter import NotificationCenter


def notifies(did, will=None):
    """Bracket a capability's public method with notifications.

    Posts `will` (when the operation changes the instrument) before the call and
    `did` after it, whether the call succeeded or not: an observer that saw a
    will always sees the matching did, so it never has to guess whether an
    operation is still running.

    user_info carries the method's arguments by name, plus "result" and "error".
    On success "error" is None; when the hook raises, "result" is None, "error"
    holds the exception, and the exception is then re-raised as it was -- a
    driver's own exception type is part of its contract, and the library must
    not disguise it. An observer decides what to do from the presence of an
    error; a caller still gets the exception.
    """
    def decorator(method):
        signature = inspect.signature(method)
        takesArguments = len(signature.parameters) > 1

        @functools.wraps(method)
        def wrapper(self, *args, **keywordArguments):
            arguments = {}
            if takesArguments:
                bound = signature.bind(self, *args, **keywordArguments)
                bound.apply_defaults()
                arguments = dict(bound.arguments)
                arguments.pop("self")

            center = NotificationCenter()
            if will is not None:
                center.post_notification(will, notifying_object=self,
                                         user_info=dict(arguments))
            try:
                result = method(self, *args, **keywordArguments)
            except Exception as error:
                center.post_notification(
                    did, notifying_object=self,
                    user_info={**arguments, "result": None, "error": error})
                raise
            center.post_notification(
                did, notifying_object=self,
                user_info={**arguments, "result": result, "error": None})
            return result

        return wrapper

    return decorator


class Capability(ABC):
    # Capability mixins are combined with a PhysicalDevice subclass, which sits
    # ahead of them in the MRO. PhysicalDevice is a cooperative base (it calls
    # super().__init__() after consuming the device-identity arguments), so a
    # mixin that holds per-instance state may define __init__ as long as it
    # takes no required arguments and forwards with super().__init__().

    # The <Capability>Notification enum each mixin posts, so that
    # allCapabilities() also enumerates every notification the library defines.
    notification = None


# ---------------------------------------------------------------------------
# Laser source capabilities
# ---------------------------------------------------------------------------

class OnOffNotification(Enum):
    willTurnOn        = "willTurnOn"
    didTurnOn         = "didTurnOn"
    willTurnOff       = "willTurnOff"
    didTurnOff        = "didTurnOff"
    didGetOnOffState  = "didGetOnOffState"


class OnOffCapability(Capability):
    notification = OnOffNotification

    @notifies(did=OnOffNotification.didGetOnOffState)
    def isLaserOn(self) -> bool:
        return self.doGetOnOffState()

    @notifies(will=OnOffNotification.willTurnOn, did=OnOffNotification.didTurnOn)
    def turnOn(self):
        self.doTurnOn()

    @notifies(will=OnOffNotification.willTurnOff, did=OnOffNotification.didTurnOff)
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


class ShutterNotification(Enum):
    willOpenShutter    = "willOpenShutter"
    didOpenShutter     = "didOpenShutter"
    willCloseShutter   = "willCloseShutter"
    didCloseShutter    = "didCloseShutter"
    didGetShutterState = "didGetShutterState"


class ShutterCapability(Capability):
    # Distinct from OnOffCapability: the shutter is a mechanical block in front of
    # the output, so it can be opened or closed while the laser stays on.
    notification = ShutterNotification

    @notifies(did=ShutterNotification.didGetShutterState)
    def isShutterOpen(self) -> bool:
        return self.doGetShutterState()

    @notifies(will=ShutterNotification.willOpenShutter, did=ShutterNotification.didOpenShutter)
    def openShutter(self):
        self.doOpenShutter()

    @notifies(will=ShutterNotification.willCloseShutter, did=ShutterNotification.didCloseShutter)
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


class PowerNotification(Enum):
    willSetPower = "willSetPower"
    didSetPower  = "didSetPower"
    didGetPower  = "didGetPower"


class PowerCapability(Capability):
    unit = "W"
    isReadable = True
    isWritable = True
    notification = PowerNotification

    @notifies(will=PowerNotification.willSetPower, did=PowerNotification.didSetPower)
    def setPower(self, power: float):
        return self.doSetPower(power)

    @notifies(did=PowerNotification.didGetPower)
    def power(self) -> float:
        return self.doGetPower()

    @abstractmethod
    def doSetPower(self, power: float):
        ...

    @abstractmethod
    def doGetPower(self) -> float:
        ...


class InterlockNotification(Enum):
    didGetInterlockState = "didGetInterlockState"


class InterlockCapability(Capability):
    isReadable = True
    isWritable = False
    notification = InterlockNotification

    @notifies(did=InterlockNotification.didGetInterlockState)
    def interlock(self) -> bool:
        return self.doGetInterlockState()

    @abstractmethod
    def doGetInterlockState(self) -> bool:
        ...


class AutostartNotification(Enum):
    willTurnAutostartOn  = "willTurnAutostartOn"
    didTurnAutostartOn   = "didTurnAutostartOn"
    willTurnAutostartOff = "willTurnAutostartOff"
    didTurnAutostartOff  = "didTurnAutostartOff"
    didGetAutostart      = "didGetAutostart"


class AutostartCapability(Capability):
    notification = AutostartNotification

    @notifies(did=AutostartNotification.didGetAutostart)
    def autostartIsOn(self) -> bool:
        return self.doGetAutostart()

    @notifies(will=AutostartNotification.willTurnAutostartOn,
              did=AutostartNotification.didTurnAutostartOn)
    def turnAutostartOn(self):
        self.doTurnAutostartOn()

    @notifies(will=AutostartNotification.willTurnAutostartOff,
              did=AutostartNotification.didTurnAutostartOff)
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


class WavelengthNotification(Enum):
    willSetWavelength     = "willSetWavelength"
    didSetWavelength      = "didSetWavelength"
    didGetWavelength      = "didGetWavelength"
    didGetWavelengthRange = "didGetWavelengthRange"


class WavelengthCapability(Capability):
    unit = "nm"
    isReadable = True
    isWritable = True
    notification = WavelengthNotification

    @notifies(will=WavelengthNotification.willSetWavelength,
              did=WavelengthNotification.didSetWavelength)
    def setWavelength(self, wavelength: float):
        return self.doSetWavelength(wavelength)

    @notifies(did=WavelengthNotification.didGetWavelength)
    def wavelength(self) -> float:
        return self.doGetWavelength()

    @notifies(did=WavelengthNotification.didGetWavelengthRange)
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


class DispersionNotification(Enum):
    willSetDispersion     = "willSetDispersion"
    didSetDispersion      = "didSetDispersion"
    didGetDispersion      = "didGetDispersion"
    didGetDispersionRange = "didGetDispersionRange"


class DispersionCapability(Capability):
    unit = "fs^2"  # group delay dispersion (GDD)
    isReadable = True
    isWritable = True
    notification = DispersionNotification

    @notifies(will=DispersionNotification.willSetDispersion,
              did=DispersionNotification.didSetDispersion)
    def setDispersion(self, dispersion: float):
        return self.doSetDispersion(dispersion)

    @notifies(did=DispersionNotification.didGetDispersion)
    def dispersion(self) -> float:
        return self.doGetDispersion()

    @notifies(did=DispersionNotification.didGetDispersionRange)
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

class WavelengthCalibrationNotification(Enum):
    willSetCalibrationWavelength = "willSetCalibrationWavelength"
    didSetCalibrationWavelength  = "didSetCalibrationWavelength"
    didGetCalibrationWavelength  = "didGetCalibrationWavelength"


class WavelengthCalibrationCapability(Capability):
    unit = "nm"
    isReadable = True
    isWritable = True
    notification = WavelengthCalibrationNotification

    def __init__(self):
        super().__init__()
        self.calibrationWavelength = None

    @notifies(did=WavelengthCalibrationNotification.didGetCalibrationWavelength)
    def getCalibrationWavelength(self):
        self.doGetCalibrationWavelength()
        return self.calibrationWavelength

    @notifies(will=WavelengthCalibrationNotification.willSetCalibrationWavelength,
              did=WavelengthCalibrationNotification.didSetCalibrationWavelength)
    def setCalibrationWavelength(self, wavelength):
        self.doSetCalibrationWavelength(wavelength)
        self.doGetCalibrationWavelength()

    @abstractmethod
    def doGetCalibrationWavelength(self):
        ...

    @abstractmethod
    def doSetCalibrationWavelength(self, wavelength):
        ...


class AutoScaleNotification(Enum):
    willTurnAutoScaleOn  = "willTurnAutoScaleOn"
    didTurnAutoScaleOn   = "didTurnAutoScaleOn"
    willTurnAutoScaleOff = "willTurnAutoScaleOff"
    didTurnAutoScaleOff  = "didTurnAutoScaleOff"
    didGetAutoScale      = "didGetAutoScale"


class AutoScaleCapability(Capability):
    # The meter picks its measurement range automatically when auto-scaling is
    # on; turning it off pins the range to whatever scale is active. A meter may
    # also expose ScaleCapability to choose that range by hand.
    notification = AutoScaleNotification

    @notifies(did=AutoScaleNotification.didGetAutoScale)
    def autoScaleIsOn(self) -> bool:
        return self.doGetAutoScale()

    @notifies(will=AutoScaleNotification.willTurnAutoScaleOn,
              did=AutoScaleNotification.didTurnAutoScaleOn)
    def turnAutoScaleOn(self):
        self.doTurnAutoScaleOn()

    @notifies(will=AutoScaleNotification.willTurnAutoScaleOff,
              did=AutoScaleNotification.didTurnAutoScaleOff)
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


class ScaleNotification(Enum):
    willSetScale         = "willSetScale"
    didSetScale          = "didSetScale"
    didGetScale          = "didGetScale"
    didGetAvailableScales = "didGetAvailableScales"


class ScaleCapability(Capability):
    # The full-scale measurement range (e.g. 200e-3 W). Independent of
    # AutoScaleCapability: setting a scale by hand generally requires auto-scaling
    # off.
    unit = "W"
    isReadable = True
    isWritable = True
    notification = ScaleNotification

    def __init__(self):
        super().__init__()
        self.scale = None

    @notifies(did=ScaleNotification.didGetScale)
    def getScale(self):
        self.doGetScale()
        return self.scale

    @notifies(will=ScaleNotification.willSetScale, did=ScaleNotification.didSetScale)
    def setScale(self, scale):
        self.doSetScale(scale)
        self.doGetScale()

    @notifies(did=ScaleNotification.didGetAvailableScales)
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

class AnalogNotification(Enum):
    """Posted by every analog capability: input, output, the combined IO, and
    streaming. One enum for the whole inheritance chain, so a device mixing in
    AnalogIOCapability and the plain AnalogOutputCapability post the very same
    member and an observer registers once."""

    didGetAnalogVoltage    = "didGetAnalogVoltage"
    willSetAnalogVoltage   = "willSetAnalogVoltage"
    didSetAnalogVoltage    = "didSetAnalogVoltage"
    willConfigureAnalogIO  = "willConfigureAnalogIO"
    didConfigureAnalogIO   = "didConfigureAnalogIO"
    willSetAnalogDirection = "willSetAnalogDirection"
    didSetAnalogDirection  = "didSetAnalogDirection"
    didGetAnalogDirection  = "didGetAnalogDirection"
    willConfigureStream    = "willConfigureStream"
    didConfigureStream     = "didConfigureStream"
    willStartStream        = "willStartStream"
    didStartStream         = "didStartStream"
    willStopStream         = "willStopStream"
    didStopStream          = "didStopStream"
    willAcquireWaveform    = "willAcquireWaveform"
    didAcquireWaveform     = "didAcquireWaveform"
    didReadStream          = "didReadStream"


class AnalogInputCapability(Capability):
    """Analog input capability (ADC). Combine with PhysicalDevice in a driver."""

    notification = AnalogNotification

    @notifies(did=AnalogNotification.didGetAnalogVoltage)
    def getAnalogVoltage(self, channel):
        """Returns the voltage measured on channel, in volts."""
        return self.doGetAnalogVoltage(channel)

    @abstractmethod
    def doGetAnalogVoltage(self, channel):
        ...


class AnalogOutputCapability(Capability):
    """Analog output capability (DAC). Combine with PhysicalDevice in a driver."""

    notification = AnalogNotification

    @notifies(will=AnalogNotification.willSetAnalogVoltage,
              did=AnalogNotification.didSetAnalogVoltage)
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

    notification = AnalogNotification

    @notifies(will=AnalogNotification.willConfigureAnalogIO,
              did=AnalogNotification.didConfigureAnalogIO)
    def configureAnalogIO(self, parameters: dict):
        """Apply the driver-specific analog configuration in parameters."""
        return self.doConfigureAnalogIO(parameters)

    @notifies(did=AnalogNotification.didGetAnalogDirection)
    def getAnalogDirection(self, channel):
        """Returns whether channel is configured as an input or an output."""
        return self.doGetAnalogDirection(channel)

    @notifies(will=AnalogNotification.willSetAnalogDirection,
              did=AnalogNotification.didSetAnalogDirection)
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

    notification = AnalogNotification

    @notifies(will=AnalogNotification.willConfigureStream,
              did=AnalogNotification.didConfigureStream)
    def configureStream(self, channels, sampleRate=None, **parameters):
        """Set up a hardware-timed acquisition of channels at sampleRate (Hz).

        Any further keyword argument is passed on to the driver, which is where
        instrument-specific options live (the SR830 takes a sampleClock, for
        instance). A driver that ignores sampleRate, because its clock is
        external, accepts None for it.
        """
        return self.doConfigureStream(channels, sampleRate, **parameters)

    @notifies(will=AnalogNotification.willStartStream,
              did=AnalogNotification.didStartStream)
    def startStream(self):
        """Start the configured acquisition."""
        return self.doStartStream()

    @notifies(did=AnalogNotification.didReadStream)
    def readStream(self):
        """Returns the samples acquired since the last read, as {channel: [volts, ...]}."""
        return self.doReadStream()

    @notifies(will=AnalogNotification.willStopStream,
              did=AnalogNotification.didStopStream)
    def stopStream(self):
        """Stop the acquisition and release any hardware streaming resources."""
        return self.doStopStream()

    @notifies(will=AnalogNotification.willAcquireWaveform,
              did=AnalogNotification.didAcquireWaveform)
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


class PhaseLockedDetectionNotification(Enum):
    willSetInputSource           = "willSetInputSource"
    didSetInputSource            = "didSetInputSource"
    willSetSensitivity           = "willSetSensitivity"
    didSetSensitivity            = "didSetSensitivity"
    willSetTimeConstant          = "willSetTimeConstant"
    didSetTimeConstant           = "didSetTimeConstant"
    didGetInPhaseVoltage         = "didGetInPhaseVoltage"
    didGetQuadratureVoltage      = "didGetQuadratureVoltage"
    didGetMagnitude              = "didGetMagnitude"
    didGetPhase                  = "didGetPhase"
    didGetReferenceFrequency     = "didGetReferenceFrequency"
    didGetInputSource            = "didGetInputSource"
    didGetSensitivity            = "didGetSensitivity"
    didGetTimeConstant           = "didGetTimeConstant"
    didGetSupportedInputSources  = "didGetSupportedInputSources"
    didGetSupportedSensitivities = "didGetSupportedSensitivities"
    didGetSupportedTimeConstants = "didGetSupportedTimeConstants"
    didGetDemodulatedValues      = "didGetDemodulatedValues"


class PhaseLockedDetectionCapability(Capability):
    """Phase-locked (lock-in) detection capability. Combine with PhysicalDevice.

    Reads the demodulated outputs (X, Y, R, theta) and reference frequency, and
    configures the signal input source, sensitivity (full-scale, in volts), and
    time constant (in seconds). Sensitivity and time constant are expressed in
    physical units so no instrument's discrete step encoding leaks into the
    contract; a driver snaps a requested value to its nearest supported step.
    """

    notification = PhaseLockedDetectionNotification

    @notifies(did=PhaseLockedDetectionNotification.didGetInPhaseVoltage)
    def getInPhaseVoltage(self):
        """Returns the in-phase component X, in volts."""
        return self.doGetInPhaseVoltage()

    @notifies(did=PhaseLockedDetectionNotification.didGetQuadratureVoltage)
    def getQuadratureVoltage(self):
        """Returns the quadrature component Y, in volts."""
        return self.doGetQuadratureVoltage()

    @notifies(did=PhaseLockedDetectionNotification.didGetMagnitude)
    def getMagnitude(self):
        """Returns the magnitude R = sqrt(X^2 + Y^2), in volts."""
        return self.doGetMagnitude()

    @notifies(did=PhaseLockedDetectionNotification.didGetPhase)
    def getPhase(self):
        """Returns the phase theta, in degrees."""
        return self.doGetPhase()

    @notifies(did=PhaseLockedDetectionNotification.didGetReferenceFrequency)
    def getReferenceFrequency(self):
        """Returns the reference frequency, in Hz."""
        return self.doGetReferenceFrequency()

    @notifies(did=PhaseLockedDetectionNotification.didGetInputSource)
    def getInputSource(self) -> InputSource:
        """Returns the signal input the demodulator currently measures."""
        return self.doGetInputSource()

    @notifies(will=PhaseLockedDetectionNotification.willSetInputSource,
              did=PhaseLockedDetectionNotification.didSetInputSource)
    def setInputSource(self, source: InputSource):
        """Select which signal input (an InputSource member) the demodulator measures."""
        return self.doSetInputSource(source)

    @notifies(did=PhaseLockedDetectionNotification.didGetSensitivity)
    def getSensitivity(self):
        """Returns the full-scale sensitivity, in volts."""
        return self.doGetSensitivity()

    @notifies(will=PhaseLockedDetectionNotification.willSetSensitivity,
              did=PhaseLockedDetectionNotification.didSetSensitivity)
    def setSensitivity(self, volts):
        """Set the full-scale sensitivity to the nearest supported step, in volts."""
        return self.doSetSensitivity(volts)

    @notifies(did=PhaseLockedDetectionNotification.didGetTimeConstant)
    def getTimeConstant(self):
        """Returns the time constant, in seconds."""
        return self.doGetTimeConstant()

    @notifies(will=PhaseLockedDetectionNotification.willSetTimeConstant,
              did=PhaseLockedDetectionNotification.didSetTimeConstant)
    def setTimeConstant(self, seconds):
        """Set the time constant to the nearest supported step, in seconds."""
        return self.doSetTimeConstant(seconds)

    @notifies(did=PhaseLockedDetectionNotification.didGetSupportedInputSources)
    def supportedInputSources(self):
        """Returns the InputSource members this instrument supports, or None."""
        return self.doGetSupportedInputSources()

    @notifies(did=PhaseLockedDetectionNotification.didGetSupportedSensitivities)
    def supportedSensitivities(self):
        """Returns the full-scale sensitivities (volts) this instrument supports, or None."""
        return self.doGetSupportedSensitivities()

    @notifies(did=PhaseLockedDetectionNotification.didGetSupportedTimeConstants)
    def supportedTimeConstants(self):
        """Returns the time constants (seconds) this instrument supports, or None."""
        return self.doGetSupportedTimeConstants()

    @notifies(did=PhaseLockedDetectionNotification.didGetDemodulatedValues)
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


class TriggerNotification(Enum):
    willSetTriggerSource        = "willSetTriggerSource"
    didSetTriggerSource         = "didSetTriggerSource"
    willSoftwareTrigger         = "willSoftwareTrigger"
    didSoftwareTrigger          = "didSoftwareTrigger"
    didGetTriggerSource         = "didGetTriggerSource"
    didGetSupportedTriggerSources = "didGetSupportedTriggerSources"


class TriggerCapability(Capability):
    """Capability for a device whose acquisition can be armed to a trigger.

    setTriggerSource selects an internal (immediate) start versus waiting for an
    external hardware trigger, and softwareTrigger() issues a manual trigger edge
    (equivalent to a pulse on the external trigger line). Combine with
    PhysicalDevice in a driver.
    """

    notification = TriggerNotification

    @notifies(will=TriggerNotification.willSetTriggerSource,
              did=TriggerNotification.didSetTriggerSource)
    def setTriggerSource(self, source: 'TriggerSource'):
        """Select whether the acquisition starts immediately or on an external trigger."""
        return self.doSetTriggerSource(source)

    @notifies(did=TriggerNotification.didGetTriggerSource)
    def getTriggerSource(self) -> 'TriggerSource':
        """Returns the currently selected TriggerSource."""
        return self.doGetTriggerSource()

    @notifies(will=TriggerNotification.willSoftwareTrigger,
              did=TriggerNotification.didSoftwareTrigger)
    def softwareTrigger(self):
        """Issue a manual (software) trigger edge."""
        return self.doSoftwareTrigger()

    @notifies(did=TriggerNotification.didGetSupportedTriggerSources)
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


class DigitalNotification(Enum):
    """Posted by every digital capability: input, output, and the combined IO.
    One enum for the whole inheritance chain (see AnalogNotification)."""

    didGetDigitalValue      = "didGetDigitalValue"
    willSetDigitalValue     = "willSetDigitalValue"
    didSetDigitalValue      = "didSetDigitalValue"
    willConfigureDigitalIO  = "willConfigureDigitalIO"
    didConfigureDigitalIO   = "didConfigureDigitalIO"
    willSetDigitalDirection = "willSetDigitalDirection"
    didSetDigitalDirection  = "didSetDigitalDirection"
    didGetDigitalDirection  = "didGetDigitalDirection"


class DigitalInputCapability(Capability):
    """Digital input capability. Combine with PhysicalDevice in a driver."""

    notification = DigitalNotification

    @notifies(did=DigitalNotification.didGetDigitalValue)
    def getDigitalValue(self, channel):
        """Returns the logic level read on channel."""
        return self.doGetDigitalValue(channel)

    @abstractmethod
    def doGetDigitalValue(self, channel):
        ...


class DigitalOutputCapability(Capability):
    """Digital output capability. Combine with PhysicalDevice in a driver."""

    notification = DigitalNotification

    @notifies(will=DigitalNotification.willSetDigitalValue,
              did=DigitalNotification.didSetDigitalValue)
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

    notification = DigitalNotification

    @notifies(will=DigitalNotification.willConfigureDigitalIO,
              did=DigitalNotification.didConfigureDigitalIO)
    def configureDigitalIO(self, parameters: dict):
        """Apply the driver-specific digital configuration in parameters."""
        return self.doConfigureDigitalIO(parameters)

    @notifies(did=DigitalNotification.didGetDigitalDirection)
    def getDigitalDirection(self, channel):
        """Returns whether channel is configured as an input or an output."""
        return self.doGetDigitalDirection(channel)

    @notifies(will=DigitalNotification.willSetDigitalDirection,
              did=DigitalNotification.didSetDigitalDirection)
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


class OutletSwitchingNotification(Enum):
    willSetOutletState = "willSetOutletState"
    didSetOutletState  = "didSetOutletState"
    didGetOutletState  = "didGetOutletState"
    didGetOutletCount  = "didGetOutletCount"


class OutletSwitchingCapability(Capability):
    """Switch individual outlets on and off and read their state.

    Outlets are addressed by their physical label (1-based): the first
    switchable outlet is outlet 1. Some strips also carry an always-on outlet
    that is not switchable and is not counted here.

    turnOutletOn, turnOutletOff and setOutletState share one hook, so they share
    one will/did pair; the outlet and its requested state are in the user_info.
    """

    notification = OutletSwitchingNotification

    @notifies(will=OutletSwitchingNotification.willSetOutletState,
              did=OutletSwitchingNotification.didSetOutletState)
    def turnOutletOn(self, outlet: int):
        self.doSetOutletState(outlet, True)

    @notifies(will=OutletSwitchingNotification.willSetOutletState,
              did=OutletSwitchingNotification.didSetOutletState)
    def turnOutletOff(self, outlet: int):
        self.doSetOutletState(outlet, False)

    @notifies(will=OutletSwitchingNotification.willSetOutletState,
              did=OutletSwitchingNotification.didSetOutletState)
    def setOutletState(self, outlet: int, isOn: bool):
        self.doSetOutletState(outlet, isOn)

    @notifies(did=OutletSwitchingNotification.didGetOutletState)
    def isOutletOn(self, outlet: int) -> bool:
        return self.doGetOutletState(outlet)

    @property
    @notifies(did=OutletSwitchingNotification.didGetOutletCount)
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


class DefaultOutletNotification(Enum):
    willSetOutletDefaultState = "willSetOutletDefaultState"
    didSetOutletDefaultState  = "didSetOutletDefaultState"


class DefaultOutletCapability(Capability):
    """Set the power-on (boot) state of individual outlets.

    Distinct from OutletSwitchingCapability: this configures the state each
    outlet powers up in after the strip loses and regains mains power, not its
    state right now.
    """

    notification = DefaultOutletNotification

    @notifies(will=DefaultOutletNotification.willSetOutletDefaultState,
              did=DefaultOutletNotification.didSetOutletDefaultState)
    def setOutletDefaultOn(self, outlet: int):
        self.doSetOutletDefaultState(outlet, True)

    @notifies(will=DefaultOutletNotification.willSetOutletDefaultState,
              did=DefaultOutletNotification.didSetOutletDefaultState)
    def setOutletDefaultOff(self, outlet: int):
        self.doSetOutletDefaultState(outlet, False)

    @notifies(will=DefaultOutletNotification.willSetOutletDefaultState,
              did=DefaultOutletNotification.didSetOutletDefaultState)
    def setOutletDefaultState(self, outlet: int, isOn: bool):
        self.doSetOutletDefaultState(outlet, isOn)

    @abstractmethod
    def doSetOutletDefaultState(self, outlet: int, isOn: bool):
        ...


class CurrentMeteringNotification(Enum):
    willResetAccumulatedCharge = "willResetAccumulatedCharge"
    didResetAccumulatedCharge  = "didResetAccumulatedCharge"
    didGetCurrent              = "didGetCurrent"
    didGetAccumulatedCharge    = "didGetAccumulatedCharge"


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
    notification = CurrentMeteringNotification

    @notifies(did=CurrentMeteringNotification.didGetCurrent)
    def current(self) -> float:
        return self.doGetCurrent()

    @notifies(did=CurrentMeteringNotification.didGetAccumulatedCharge)
    def accumulatedCharge(self) -> float:
        return self.doGetAccumulatedCharge()

    @notifies(will=CurrentMeteringNotification.willResetAccumulatedCharge,
              did=CurrentMeteringNotification.didResetAccumulatedCharge)
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
