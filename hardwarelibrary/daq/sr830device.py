import math
import re
from enum import Enum

from serial.tools.list_ports import comports

from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.communication.prologixgpibport import PrologixGPIBPort
from hardwarelibrary.communication.communicationport import (
    CommunicationPort, CommunicationReadTimeout,
)
from hardwarelibrary.capabilities import (
    AnalogInputStreamCapability, AnalogOutputCapability, PhaseLockedDetectionCapability,
    TriggerCapability, InputSource, TriggerSource, SampleClock,
)

FLOAT_PATTERN = r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
INTEGER_PATTERN = r"(-?\d+)"

# SR830 SENS command steps (full-scale sensitivity in volts) and OFLT command
# steps (time constant in seconds). The list index is the command argument.
SR830_SENSITIVITIES = [
    2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9,
    1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6,
    1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3,
    1.0,
]
SR830_TIME_CONSTANTS = [
    10e-6, 30e-6, 100e-6, 300e-6,
    1e-3, 3e-3, 10e-3, 30e-3,
    100e-3, 300e-3, 1.0, 3.0,
    10.0, 30.0, 100.0, 300.0,
    1e3, 3e3, 10e3, 30e3,
]

# SR830 SRAT command steps: data-buffer sample rate in Hz, index = argument.
# Index 14 ("Trigger") is the external per-sample clock, handled separately.
SR830_SAMPLE_RATES = [
    0.0625, 0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512,
]

class AuxInput(Enum):
    """The SR830's four auxiliary A/D inputs (rear panel). The value is the
    OAUX? channel number."""

    Aux1 = 1
    Aux2 = 2
    Aux3 = 3
    Aux4 = 4


class AuxOutput(Enum):
    """The SR830's four auxiliary D/A outputs (rear panel). The value is the
    AUXV channel number."""

    Aux1 = 1
    Aux2 = 2
    Aux3 = 3
    Aux4 = 4


_INPUT_SOURCE_TO_INDEX = {
    InputSource.SingleEnded: 0,
    InputSource.Differential: 1,
    InputSource.Current1M: 2,
    InputSource.Current100M: 3,
}
_INDEX_TO_INPUT_SOURCE = {index: source for source, index in _INPUT_SOURCE_TO_INDEX.items()}

_TRIGGER_SOURCE_TO_INDEX = {TriggerSource.Internal: 0, TriggerSource.External: 1}
_INDEX_TO_TRIGGER_SOURCE = {index: source for source, index in _TRIGGER_SOURCE_TO_INDEX.items()}


class StreamChannel(Enum):
    """A quantity the SR830 can record into its data buffer. The SR830 buffers
    exactly the two front-panel displays (CH1, CH2), so X and R share CH1 while
    Y and Theta share CH2: a stream may hold at most one CH1 and one CH2
    quantity."""

    X = "X"
    Y = "Y"
    R = "R"
    Theta = "Theta"


# Each StreamChannel maps to (display number, DDEF quantity index) per the SR830
# DDEF command: CH1 j=0 X / j=1 R; CH2 j=0 Y / j=1 theta.
_STREAM_CHANNEL_TO_DISPLAY = {
    StreamChannel.X:     (1, 0),
    StreamChannel.R:     (1, 1),
    StreamChannel.Y:     (2, 0),
    StreamChannel.Theta: (2, 1),
}


class SR830Device(PhysicalDevice, AnalogInputStreamCapability, AnalogOutputCapability,
                  PhaseLockedDetectionCapability, TriggerCapability):
    """Stanford Research Systems SR830 DSP lock-in amplifier over a Prologix
    GPIB-USB controller.

    The SR830 is a GPIB instrument; the Prologix adaptor bridges it to a host
    serial port (a generic FTDI cable, VID 0x0403 / PID 0x6001), so this driver
    talks to a PrologixGPIBPort with the ordinary readString/writeString
    primitives. It exposes several capabilities: AnalogInputStreamCapability for the
    four rear-panel Aux A/D inputs (OAUX?, 1-4) plus hardware-timed buffered
    acquisition of the demodulated outputs (the internal data buffer),
    AnalogOutputCapability for the four rear-panel Aux D/A outputs (AUXV, 1-4),
    PhaseLockedDetectionCapability for the demodulated outputs (X, Y, R, theta via
    OUTP?/SNAP?), the signal input source (ISRC), and the sensitivity and
    time-constant settings, and TriggerCapability for the rear-panel TRIG IN. The
    Aux inputs and outputs are general-purpose and independent of the lock-in
    signal path.
    """

    classIdVendor = 0x0403
    classIdProduct = 0x6001
    usesGenericSerialConverter = True

    sensitivities = SR830_SENSITIVITIES
    timeConstants = SR830_TIME_CONSTANTS
    sampleRates = SR830_SAMPLE_RATES
    minAuxOutputVoltage = -10.5
    maxAuxOutputVoltage = 10.5

    def __init__(self, gpibAddress=8, portPath=None, serialNumber=None,
                 idProduct=0x6001, idVendor=0x0403):
        """Create an SR830 driver. gpibAddress is the SR830's GPIB address (8 is
        the factory default). portPath, if given, names the Prologix adaptor's
        serial port directly; otherwise the adaptor is discovered by its FTDI
        idVendor/idProduct, narrowed by serialNumber when one is provided."""
        super().__init__(serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.gpibAddress = gpibAddress
        self.portPath = portPath
        self.idn = None
        self._streamChannels = []
        self._streamReadIndex = 0

    def doInitializeDevice(self):
        """Find the SR830 among the FTDI adaptors, open it, and confirm identity.

        Several instruments share the generic FTDI 0x0403:0x6001 identity (the
        Prologix adaptor, plain RS-232 cables, ...), so VID/PID alone cannot pick
        out the SR830. Confirming identity is exactly this method's job: it probes
        each candidate adaptor with *IDN? and keeps the one that answers as an
        SR830, raising UnableToInitialize if none does. Once found, the adaptor's
        serial number is pinned so a later reconnect goes straight to it.
        """
        candidates = self._candidateAdaptors()
        if not candidates:
            raise PhysicalDevice.UnableToInitialize(
                "No Prologix GPIB-USB adaptor (FTDI {0:#06x}:{1:#06x}) found for the "
                "SR830".format(self.idVendor, self.idProduct))

        lastError = None
        for candidatePath, candidateSerial in candidates:
            port = PrologixGPIBPort(gpibAddress=self.gpibAddress, portPath=candidatePath)
            try:
                port.open()
                self.port = port
                self.readIdentity()
                if self.idn is not None and "SR830" in self.idn:
                    # Pin the adaptor so a later reconnect selects it directly by
                    # VID/PID + serial number instead of probing every adaptor.
                    if candidateSerial is not None:
                        self.serialNumber = candidateSerial
                    return
                lastError = "{0} answered *IDN?={1!r}".format(candidatePath, self.idn)
            except Exception as error:
                lastError = "{0}: {1}".format(candidatePath, error)
            if port.isOpen:
                port.close()
            self.port = None

        raise PhysicalDevice.UnableToInitialize(
            "No SR830 found at GPIB address {0} on any FTDI adaptor ({1})".format(
                self.gpibAddress, lastError))

    def _candidateAdaptors(self):
        """The (portPath, serialNumber) adaptors to probe for the SR830.

        An explicit portPath is the only candidate. Otherwise every connected
        FTDI adaptor matching this device's VID/PID is a candidate, narrowed by
        serialNumber when one is known (PhysicalDevice turns the default into
        ".*", which matches any)."""
        if self.portPath is not None:
            return [(self.portPath, None)]

        serialNumber = None if self.serialNumber in (None, ".*") else self.serialNumber
        candidates = []
        for port in comports():
            if port.vid != self.idVendor or port.pid != self.idProduct:
                continue
            if serialNumber is not None and (port.serial_number is None
                    or not re.search(serialNumber, port.serial_number, re.IGNORECASE)):
                continue
            candidates.append((port.device, port.serial_number))
        return candidates

    def doShutdownDevice(self):
        """Close the Prologix port and drop the reference to it."""
        if self.port is not None:
            self.port.close()
            self.port = None

    def writeCommand(self, command):
        """Send a command that expects no reply, appending the GPIB terminator."""
        self.port.writeString(command + "\n")

    def query(self, command) -> str:
        """Send command and return its reply as a stripped string.

        The write and the read are held under the port's transactionLock so a
        concurrent caller cannot interleave and read this command's reply.
        """
        with self.port.transactionLock:
            self.port.writeString(command + "\n")
            return self.port.readString().strip()

    def queryFloat(self, command) -> float:
        """Send command and return the first floating-point number in the reply."""
        _, group = self.port.writeStringReadFirstMatchingGroup(
            command + "\n", replyPattern=FLOAT_PATTERN)
        return float(group)

    def queryInteger(self, command) -> int:
        """Send command and return the first integer in the reply."""
        _, group = self.port.writeStringReadFirstMatchingGroup(
            command + "\n", replyPattern=INTEGER_PATTERN)
        return int(group)

    def readIdentity(self) -> str:
        """Query *IDN?, cache it in self.idn, and return the identity string."""
        self.idn = self.query("*IDN?")
        return self.idn

    def getAnalogVoltage(self, channel):
        """Read an Aux Input, in volts (SR830 OAUX?). channel is an AuxInput
        member; a bare 1-4 is also accepted and coerced, and anything else
        raises ValueError."""
        channel = AuxInput(channel)
        return self.queryFloat("OAUX? {0}".format(channel.value))

    def setAnalogVoltage(self, value, channel):
        """Set an Aux Output to value volts (SR830 AUXV). channel is an AuxOutput
        member (a bare 1-4 is also accepted and coerced). value must be within
        [-10.5, 10.5] V or ValueError is raised."""
        channel = AuxOutput(channel)
        if not self.minAuxOutputVoltage <= value <= self.maxAuxOutputVoltage:
            raise ValueError(
                "SR830 Aux Output must be within [{0}, {1}] V, got {2}".format(
                    self.minAuxOutputVoltage, self.maxAuxOutputVoltage, value))
        self.writeCommand("AUXV {0},{1:.3f}".format(channel.value, value))

    def getAnalogOutputVoltage(self, channel):
        """Read back an Aux Output setpoint, in volts (SR830 AUXV?). channel is
        an AuxOutput member (a bare 1-4 is also accepted and coerced)."""
        channel = AuxOutput(channel)
        return self.queryFloat("AUXV? {0}".format(channel.value))

    def getInPhaseVoltage(self):
        """Returns the in-phase component X, in volts (SR830 OUTP? 1)."""
        return self.queryFloat("OUTP? 1")

    def getQuadratureVoltage(self):
        """Returns the quadrature component Y, in volts (SR830 OUTP? 2)."""
        return self.queryFloat("OUTP? 2")

    def getMagnitude(self):
        """Returns the magnitude R = sqrt(X^2 + Y^2), in volts (SR830 OUTP? 3)."""
        return self.queryFloat("OUTP? 3")

    def getPhase(self):
        """Returns the phase theta, in degrees (SR830 OUTP? 4)."""
        return self.queryFloat("OUTP? 4")

    def getReferenceFrequency(self):
        """Returns the reference frequency, in Hz (SR830 FREQ?)."""
        return self.queryFloat("FREQ?")

    def snap(self, *parameters):
        """Read 2 to 6 outputs at one instant (SR830 SNAP?). Parameter codes:
        1=X, 2=Y, 3=R, 4=theta, 5-8=Aux1-4, 9=reference frequency. Returns a
        tuple of floats in the requested order."""
        if not 2 <= len(parameters) <= 6:
            raise ValueError("SNAP? takes 2 to 6 parameters, got {0}".format(len(parameters)))
        command = "SNAP? " + ",".join(str(int(parameter)) for parameter in parameters)
        return tuple(float(value) for value in self.query(command).split(","))

    def getDemodulatedValues(self):
        """Read X, Y, R, and theta at one instant, plus the reference frequency.

        Overrides the base implementation to read the four outputs atomically via
        SNAP? (a single coherent timepoint) rather than four separate queries.
        """
        x, y, r, theta = self.snap(1, 2, 3, 4)
        return {"X": x, "Y": y, "R": r, "theta": theta,
                "referenceFrequency": self.getReferenceFrequency()}

    # AnalogInputStreamCapability: hardware-timed acquisition into the SR830 data
    # buffer. channels are StreamChannel members (at most one CH1 and one CH2
    # quantity). acquireWaveform (from the base) loops readStream for you.

    def configureStream(self, channels, sampleRate, sampleClock=SampleClock.Internal):
        """Set up buffered acquisition. channels is a list of StreamChannel
        members (1 or 2, not both on the same display). With an Internal
        sampleClock, sampleRate (Hz) is snapped to the nearest SRAT step. With an
        External sampleClock, one sample is taken per external clock/trigger edge
        (SRAT 14) and sampleRate is ignored. The start (immediate vs external
        trigger) is a separate concern, set via setTriggerSource."""
        channels = [StreamChannel(channel) for channel in channels]
        if not 1 <= len(channels) <= 2:
            raise ValueError("SR830 buffers 1 or 2 channels (the CH1/CH2 displays)")
        usedDisplays = set()
        for channel in channels:
            display, quantityIndex = _STREAM_CHANNEL_TO_DISPLAY[channel]
            if display in usedDisplays:
                raise ValueError(
                    "channels sharing display {0} cannot be buffered together "
                    "(e.g. X and R, or Y and Theta)".format(display))
            usedDisplays.add(display)
            self.writeCommand("DDEF {0},{1},0".format(display, quantityIndex))
        if sampleClock == SampleClock.External:
            self.writeCommand("SRAT 14")
        else:
            self.writeCommand("SRAT {0}".format(self._sampleRateIndexFor(sampleRate)))
        self.writeCommand("SEND 0")
        self._streamChannels = channels
        self._streamReadIndex = 0

    def startStream(self):
        """Clear the data buffer (REST) and start acquisition (STRT).

        With an External trigger source the SR830 arms here but does not record
        until a trigger edge arrives (softwareTrigger or the TRIG IN line).
        """
        self.writeCommand("REST")
        self._streamReadIndex = 0
        self.writeCommand("STRT")

    def readStream(self):
        """Return the samples buffered since the last read, as {channel: [volts, ...]}.

        Reads how many points the buffer holds (SPTS?) and transfers only the new
        ones (TRCA?) for each configured channel, advancing the read cursor. An
        empty list per channel means no new samples since the previous call.
        """
        available = self.queryInteger("SPTS?")
        newCount = available - self._streamReadIndex
        if newCount <= 0:
            return {channel: [] for channel in self._streamChannels}
        block = {}
        for channel in self._streamChannels:
            display = _STREAM_CHANNEL_TO_DISPLAY[channel][0]
            reply = self.query("TRCA? {0},{1},{2}".format(
                display, self._streamReadIndex, newCount))
            block[channel] = [float(value) for value in reply.split(",") if value.strip()]
        self._streamReadIndex = available
        return block

    def stopStream(self):
        """Pause acquisition into the data buffer (SR830 PAUS)."""
        self.writeCommand("PAUS")

    def supportedSampleRates(self):
        """Returns the SR830's discrete data-buffer sample rates, in Hz."""
        return list(self.sampleRates)

    def _sampleRateIndexFor(self, rate):
        """Returns the SRAT index whose rate (Hz) is closest to rate."""
        return min(range(len(self.sampleRates)),
                   key=lambda index: abs(self.sampleRates[index] - rate))

    # TriggerCapability: the rear-panel TRIG IN. setTriggerSource(External) arms
    # the scan to start on a trigger edge (TSTR); trigger() issues a software edge.

    def setTriggerSource(self, source: TriggerSource):
        """Select immediate (Internal) or external-trigger (External) scan start
        (SR830 TSTR). source must be a supported TriggerSource or ValueError is
        raised."""
        if source not in _TRIGGER_SOURCE_TO_INDEX:
            raise ValueError("Unsupported trigger source {0}".format(source))
        self.writeCommand("TSTR {0}".format(_TRIGGER_SOURCE_TO_INDEX[source]))

    def getTriggerSource(self) -> TriggerSource:
        """Returns the current scan-start TriggerSource (SR830 TSTR?)."""
        return _INDEX_TO_TRIGGER_SOURCE[self.queryInteger("TSTR?")]

    def softwareTrigger(self):
        """Issue a software trigger edge (SR830 TRIG), as if TRIG IN pulsed."""
        self.writeCommand("TRIG")

    def supportedTriggerSources(self):
        """Returns the trigger sources the SR830 supports (Internal, External)."""
        return list(TriggerSource)

    def getInputSource(self) -> InputSource:
        """Returns the demodulator's signal input source (SR830 ISRC?)."""
        return _INDEX_TO_INPUT_SOURCE[self.queryInteger("ISRC?")]

    def setInputSource(self, source: InputSource):
        """Select the demodulator's signal input source (SR830 ISRC). source must
        be a supported InputSource or ValueError is raised."""
        if source not in _INPUT_SOURCE_TO_INDEX:
            raise ValueError("Unsupported input source {0}".format(source))
        self.writeCommand("ISRC {0}".format(_INPUT_SOURCE_TO_INDEX[source]))

    def supportedInputSources(self):
        """Returns the four input sources the SR830 supports."""
        return list(InputSource)

    def getSensitivity(self):
        """Returns the current full-scale sensitivity, in volts (SR830 SENS?)."""
        return self.sensitivities[self.queryInteger("SENS?")]

    def setSensitivity(self, volts):
        """Set the full-scale sensitivity to the smallest step >= volts (SR830 SENS)."""
        self.writeCommand("SENS {0}".format(self._sensitivityIndexFor(volts)))

    def getTimeConstant(self):
        """Returns the current time constant, in seconds (SR830 OFLT?)."""
        return self.timeConstants[self.queryInteger("OFLT?")]

    def setTimeConstant(self, seconds):
        """Set the time constant to the nearest step, in seconds (SR830 OFLT)."""
        self.writeCommand("OFLT {0}".format(self._timeConstantIndexFor(seconds)))

    def supportedSensitivities(self):
        """Returns the SR830's discrete full-scale sensitivities, in volts."""
        return list(self.sensitivities)

    def supportedTimeConstants(self):
        """Returns the SR830's discrete time constants, in seconds."""
        return list(self.timeConstants)

    def _sensitivityIndexFor(self, volts):
        """Returns the SENS index for the smallest full-scale that contains volts.

        Rounding up rather than to nearest keeps a requested value that falls
        between two steps from clipping; a value above the largest step clamps to
        it.
        """
        for index, value in enumerate(self.sensitivities):
            if value >= volts:
                return index
        return len(self.sensitivities) - 1

    def _timeConstantIndexFor(self, seconds):
        """Returns the OFLT index whose time constant is closest to seconds."""
        return min(range(len(self.timeConstants)),
                   key=lambda index: abs(self.timeConstants[index] - seconds))

    def doGetStatusUserInfo(self):
        """Returns the demodulated values for the periodic status notification."""
        return self.getDemodulatedValues()


class DebugPrologixGPIBPort(CommunicationPort):
    """Hardware-free stand-in for a Prologix controller wired to an SR830.

    Follows the CommunicationPort structure: it implements only the transport
    primitives (open/close/isOpen/flush/bytesAvailable and readData/writeData
    over an in-memory buffer, like USBPort), so the inherited readString and
    writeStringReadFirstMatchingGroup drive it unchanged. writeData interprets a
    line: '++' controller commands are consumed silently, an SR830 query enqueues
    a reply, and an SR830 set mutates the simulated state.
    """

    def __init__(self):
        """Create the fake port with a plausible initial SR830 state."""
        super().__init__()
        self._isOpen = False
        self._buffer = bytearray()
        self._auxVoltages = {1: 0.10, 2: 0.20, 3: 0.30, 4: 0.40}
        self._auxOutputs = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self._x = 1.0e-3
        self._y = 2.0e-3
        self._referenceFrequency = 1.0e3
        self._sensitivityIndex = 26
        self._timeConstantIndex = 10
        self._inputIndex = 0
        self._sampleRateIndex = 4
        self._bufferMode = 0
        self._triggerStartIndex = 0
        self._scanning = False
        self._storedPoints = 0
        self._buffers = {1: [], 2: []}

    @property
    def isOpen(self):
        """True while the fake port is open."""
        return self._isOpen

    def open(self):
        """Mark the port open and clear the reply buffer."""
        self._isOpen = True
        self._buffer = bytearray()

    def close(self):
        """Mark the port closed."""
        self._isOpen = False

    def bytesAvailable(self) -> int:
        """Returns the number of bytes waiting to be read."""
        return len(self._buffer)

    def flush(self):
        """Discard any buffered reply bytes."""
        self._buffer = bytearray()

    def writeData(self, data, endPoint=None) -> int:
        """Interpret one written line and queue any reply it produces.

        Returns the number of bytes accepted. Controller ('++') lines are
        consumed silently; an SR830 query enqueues its reply, and an SR830 set
        mutates the simulated state.
        """
        line = bytes(data).decode("utf-8").strip()
        reply = self._process(line)
        if reply is not None:
            self._buffer += bytearray((reply + "\n").encode("utf-8"))
        return len(data)

    def readData(self, length, endPoint=None) -> bytearray:
        """Return length bytes from the reply buffer, or time out if too few."""
        if len(self._buffer) < length:
            raise CommunicationReadTimeout("Only obtained {0}".format(self._buffer))
        data = self._buffer[:length]
        self._buffer = self._buffer[length:]
        return data

    def _process(self, line):
        """Compute the reply for one command line (or None for no reply / a set)."""
        if line.startswith("++"):
            return None
        if line == "*IDN?":
            return "Stanford_Research_Systems,SR830,s/n12345,ver1.07"
        if line.startswith("OAUX?"):
            channel = int(line[len("OAUX?"):])
            return self._formatFloat(self._auxVoltages.get(channel, 0.0))
        if line.startswith("AUXV?"):
            channel = int(line[len("AUXV?"):])
            return self._formatFloat(self._auxOutputs.get(channel, 0.0))
        if line.startswith("AUXV "):
            channelText, voltageText = line[len("AUXV "):].split(",")
            self._auxOutputs[int(channelText)] = float(voltageText)
            return None
        if line.startswith("OUTP?"):
            return self._formatFloat(self._outputValue(int(line[len("OUTP?"):])))
        if line.startswith("SNAP?"):
            codes = [int(code) for code in line[len("SNAP?"):].split(",")]
            return ",".join(self._formatFloat(self._snapValue(code)) for code in codes)
        if line == "FREQ?":
            return self._formatFloat(self._referenceFrequency)
        if line == "SENS?":
            return str(self._sensitivityIndex)
        if line.startswith("SENS "):
            self._sensitivityIndex = int(line[len("SENS "):])
            return None
        if line == "OFLT?":
            return str(self._timeConstantIndex)
        if line.startswith("OFLT "):
            self._timeConstantIndex = int(line[len("OFLT "):])
            return None
        if line == "ISRC?":
            return str(self._inputIndex)
        if line.startswith("ISRC "):
            self._inputIndex = int(line[len("ISRC "):])
            return None
        if line.startswith("DDEF "):
            return None
        if line == "SRAT?":
            return str(self._sampleRateIndex)
        if line.startswith("SRAT "):
            self._sampleRateIndex = int(line[len("SRAT "):])
            return None
        if line.startswith("SEND "):
            self._bufferMode = int(line[len("SEND "):])
            return None
        if line == "TSTR?":
            return str(self._triggerStartIndex)
        if line.startswith("TSTR "):
            self._triggerStartIndex = int(line[len("TSTR "):])
            return None
        if line == "TRIG":
            self._storeStreamPoints(1)
            return None
        if line == "REST":
            self._storedPoints = 0
            self._buffers = {1: [], 2: []}
            self._scanning = False
            return None
        if line == "STRT":
            # Internal start (TSTR 0) runs immediately; external start (TSTR 1)
            # waits for a trigger edge, so no points accrue until trigger().
            self._scanning = self._triggerStartIndex == 0
            return None
        if line == "PAUS":
            self._scanning = False
            return None
        if line == "SPTS?":
            # An internal timebase (SRAT 0-13) accrues samples on its own; an
            # external clock (SRAT 14) only advances on a trigger edge.
            if self._scanning and self._sampleRateIndex != 14:
                self._storeStreamPoints(25)
            return str(self._storedPoints)
        if line.startswith("TRCA?"):
            display, start, count = (int(field) for field in line[len("TRCA?"):].split(","))
            values = self._buffers.get(display, [])[start:start + count]
            return ",".join(self._formatFloat(value) for value in values)
        return None

    def _storeStreamPoints(self, count):
        """Append count synthetic samples to each display buffer (a ramp so
        successive reads return distinguishable values)."""
        for display in (1, 2):
            base = {1: 1.0e-3, 2: 2.0e-3}[display]
            start = len(self._buffers[display])
            self._buffers[display].extend(base + 1e-6 * (start + i) for i in range(count))
        self._storedPoints += count

    def _outputValue(self, index):
        """Returns the simulated demodulated output for an OUTP?/SNAP? code
        (1=X, 2=Y, 3=R, 4=theta)."""
        if index == 1:
            return self._x
        if index == 2:
            return self._y
        if index == 3:
            return math.hypot(self._x, self._y)
        if index == 4:
            return math.degrees(math.atan2(self._y, self._x))
        return 0.0

    def _snapValue(self, code):
        """Returns the simulated value for a SNAP? code (1-4=X/Y/R/theta,
        5-8=Aux1-4, 9=reference frequency)."""
        if code in (1, 2, 3, 4):
            return self._outputValue(code)
        if code in (5, 6, 7, 8):
            return self._auxVoltages.get(code - 4, 0.0)
        if code == 9:
            return self._referenceFrequency
        return 0.0

    @staticmethod
    def _formatFloat(value):
        """Format a float the way the SR830 renders numeric replies."""
        return "{0:.6e}".format(value)


class DebugSR830Device(SR830Device):
    """Hardware-free SR830 for tests. Swaps the transport (DebugPrologixGPIBPort)
    so every parse/validate path in SR830Device runs unchanged."""

    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF9
    usesGenericSerialConverter = False

    def __init__(self, serialNumber="debug"):
        """Create a debug SR830 carrying the reserved debug USB identity."""
        super().__init__(gpibAddress=8, serialNumber=serialNumber,
                         idProduct=self.classIdProduct, idVendor=self.classIdVendor)

    def doInitializeDevice(self):
        """Attach the in-memory DebugPrologixGPIBPort and confirm identity.

        Overrides discovery only; every other method runs the real SR830Device
        code path against the fake port.
        """
        self.port = DebugPrologixGPIBPort()
        self.port.open()
        self.readIdentity()

    def doShutdownDevice(self):
        """Close the in-memory port and drop the reference to it."""
        if self.port is not None:
            self.port.close()
            self.port = None
