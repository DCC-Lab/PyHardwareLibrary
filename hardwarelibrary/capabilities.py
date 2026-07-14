"""Capability mixins shared by every device family.

A capability is a feature an instrument may have (turn on/off, open a shutter,
read a voltage, ...). A driver declares the capabilities it supports by mixing
them alongside a PhysicalDevice subclass; the mixin's public methods delegate to
the do* hooks (or, for some families, are themselves the abstract hook) the
driver implements. Mixins carry the *Capability suffix; only instantiable
hardware drivers are named *Device.

PhysicalDevice.capabilities() / hasCapability() introspect these by walking the
MRO for Capability subclasses, so every capability across every family must
subclass the single Capability base defined here.
"""

from abc import ABC, abstractmethod
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

    @abstractmethod
    def getAnalogVoltage(self, channel):
        ...


class AnalogOutputCapability(Capability):
    """Analog output capability (DAC). Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def setAnalogVoltage(self, value, channel):
        ...


class AnalogIOCapability(AnalogInputCapability, AnalogOutputCapability):
    """Both analog input and output.

    The configure and direction hooks are optional and default to no-ops.
    """

    def configureAnalogIO(self, parameters: dict):
        pass

    def getAnalogDirection(self, channel):
        pass

    def setAnalogDirection(self, channel):
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

    @abstractmethod
    def configureStream(self, channels, sampleRate):
        """Set up a hardware-timed acquisition of channels at sampleRate (Hz)."""
        ...

    @abstractmethod
    def startStream(self):
        """Start the configured acquisition."""
        ...

    @abstractmethod
    def readStream(self):
        """Return the samples acquired since the last read, as {channel: [volts, ...]}."""
        ...

    @abstractmethod
    def stopStream(self):
        """Stop the acquisition and release any hardware streaming resources."""
        ...

    def acquireWaveform(self, channels, sampleRate, sampleCount):
        """Acquire exactly sampleCount samples per channel, blocking until done.

        Configures, starts, and drains the stream (looping readStream) on the
        caller's behalf, then stops it; returns {channel: [volts, ...]} truncated
        to sampleCount per channel.
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

    @abstractmethod
    def getInPhaseVoltage(self):
        """Returns the in-phase component X, in volts."""
        ...

    @abstractmethod
    def getQuadratureVoltage(self):
        """Returns the quadrature component Y, in volts."""
        ...

    @abstractmethod
    def getMagnitude(self):
        """Returns the magnitude R = sqrt(X^2 + Y^2), in volts."""
        ...

    @abstractmethod
    def getPhase(self):
        """Returns the phase theta, in degrees."""
        ...

    @abstractmethod
    def getReferenceFrequency(self):
        """Returns the reference frequency, in Hz."""
        ...

    @abstractmethod
    def getInputSource(self) -> InputSource:
        """Returns the signal input the demodulator currently measures."""
        ...

    @abstractmethod
    def setInputSource(self, source: InputSource):
        """Select which signal input (an InputSource member) the demodulator measures."""
        ...

    @abstractmethod
    def getSensitivity(self):
        """Returns the full-scale sensitivity, in volts."""
        ...

    @abstractmethod
    def setSensitivity(self, volts):
        """Set the full-scale sensitivity to the nearest supported step, in volts."""
        ...

    @abstractmethod
    def getTimeConstant(self):
        """Returns the time constant, in seconds."""
        ...

    @abstractmethod
    def setTimeConstant(self, seconds):
        """Set the time constant to the nearest supported step, in seconds."""
        ...

    def supportedInputSources(self):
        """Optional: the InputSource members this instrument supports, or None."""
        return None

    def supportedSensitivities(self):
        """Optional: the full-scale sensitivities (volts) this instrument supports, or None."""
        return None

    def supportedTimeConstants(self):
        """Optional: the time constants (seconds) this instrument supports, or None."""
        return None

    def getDemodulatedValues(self):
        """One reading of all demodulated outputs plus the reference frequency.

        Built on the individual getters; a driver may override it to read the
        outputs atomically (a single coherent timepoint) when the hardware
        supports it.
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

    @abstractmethod
    def setTriggerSource(self, source: 'TriggerSource'):
        """Select whether the acquisition starts immediately or on an external trigger."""
        ...

    @abstractmethod
    def getTriggerSource(self) -> 'TriggerSource':
        """Returns the currently selected TriggerSource."""
        ...

    @abstractmethod
    def softwareTrigger(self):
        """Issue a manual (software) trigger edge."""
        ...

    def supportedTriggerSources(self):
        """Optional: the TriggerSource members this device supports, or None."""
        return None


class DigitalInputCapability(Capability):
    """Digital input capability. Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def getDigitalValue(self, channel):
        ...


class DigitalOutputCapability(Capability):
    """Digital output capability. Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def setDigitalValue(self, value, channel):
        ...


class DigitalIOCapability(DigitalInputCapability, DigitalOutputCapability):
    """Both digital input and output.

    The configure and direction hooks are optional and default to no-ops.
    """

    def configureDigitalIO(self, parameters: dict):
        pass

    def getDigitalDirection(self, channel):
        pass

    def setDigitalDirection(self, channel):
        pass
