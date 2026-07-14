from abc import ABC, abstractmethod
from enum import Enum


class DAQNotification(Enum):
    willAcquire    = "willAcquire"
    didAcquire     = "didAcquire"


class AnalogInputCapability(ABC):
    """Analog input capability (ADC). Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def getAnalogVoltage(self, channel):
        ...


class AnalogOutputCapability(ABC):
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


class PhaseLockedDetectionCapability(ABC):
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


class TriggerCapability(ABC):
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


class DigitalInputCapability(ABC):
    """Digital input capability. Combine with PhysicalDevice in a driver."""

    @abstractmethod
    def getDigitalValue(self, channel):
        ...


class DigitalOutputCapability(ABC):
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
