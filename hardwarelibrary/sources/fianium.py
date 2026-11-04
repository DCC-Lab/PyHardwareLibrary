import re

from serial.tools.list_ports import comports

from ..physicaldevice import PhysicalDevice
from ..communication.serialport import SerialPort
from ..communication.communicationport import CommunicationReadNoMatch
from .lasersourcedevice import LaserSourceDevice
from hardwarelibrary.capabilities import OnOffCapability, TemperatureCapability, PulsePickerCapability


class FianiumManualInterventionRequired(Exception):
    """Raised by doTurnOn/doTurnOff: this driver never writes M= or Q=.

    The console has a "USB open loop mode" (M=) in which Q= drives the pump
    current from software, but this driver deliberately does not use it: on
    the bench, the only mode ever observed was "Pot controlled open loop
    mode", where emission is gated by the physical "Oscillator ON" knob and
    the "LASER" key on the chassis, not by any serial command. Forcing pump
    current without a confirmed seed can self-pulse and damage the fiber
    amplifier -- see labbook/20261104-fianium-laser-nkt for the bring-up that
    established this rule.
    """


class FianiumLaserDevice(LaserSourceDevice, OnOffCapability, TemperatureCapability, PulsePickerCapability):
    """Fianium supercontinuum fiber laser (pre-NKT-acquisition unit; firmware
    identifies itself as "Issue 5.17 20th February 2012").

    Not the NKT Interbus protocol (pylablib.devices.NKT speaks that one; an
    Interbus scan on this unit finds nothing). This unit runs its own ASCII
    command-line console instead: 19200 baud, commands terminated by a lone
    '\\r' (not '\\r\\n'); 'help\\r' lists the full command set (A?/A=0, B?,
    I?/I=, M?/M=, O?, P?, Q?/Q=, R?/R=, T?, V?, W?, X?/X=).

    The console has no laser on/off command. doGetOnOffState infers emission
    from the pump drive (Q?) and the preamp photodiode (P?); doTurnOn/doTurnOff
    always raise FianiumManualInterventionRequired, because starting or
    stopping emission from software has no verified safe path on this unit
    (see that exception's docstring).

    Transport is a generic FTDI USB-serial adaptor (0x0403:0x6001), the same
    identity shared by every FTDI cable, so VID/PID alone cannot pick out this
    instrument: see PhysicalDevice.usesGenericSerialConverter. doInitializeDevice
    follows the SR830Device pattern (hardwarelibrary/daq/sr830device.py): probe
    every matching FTDI adaptor and confirm identity with a real command (V?)
    before trusting the port, rather than pinning a serial number up front.
    """

    classIdVendor = 0x0403
    classIdProduct = 0x6001
    usesGenericSerialConverter = True

    defaultBaudRate = 19200
    commandTerminator = "\r"

    # P? (preamp photodiode) above this means the seed/preamp stage is running;
    # below is the noise floor. Empirical, observed on one unit: noise 8-14,
    # active 2207 once the oscillator was started (labbook/20261104-fianium-laser-nkt).
    seedDetectionThreshold = 100

    def __init__(self, portPath=None, serialNumber=None, idProduct=None, idVendor=None):
        super().__init__(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.portPath = portPath
        self.port = None
        self.firmwareVersion = None

    def doInitializeDevice(self):
        """Probe every candidate FTDI adaptor and keep the one that answers
        V? as a Fianium. See the class docstring: VID/PID alone cannot
        identify this instrument, so this method is the actual identity
        check, not the adaptor's serial number.
        """
        candidates = self._candidateAdaptors()
        if not candidates:
            raise PhysicalDevice.UnableToInitialize(
                "No FTDI adaptor (idVendor={0:#06x}, idProduct={1:#06x}) found for "
                "the Fianium".format(self.idVendor, self.idProduct))

        lastError = None
        for candidatePath, candidateSerial in candidates:
            port = SerialPort(portPath=candidatePath)
            try:
                port.open(baudRate=self.defaultBaudRate, timeout=0.5)
                self.port = port
                self.readIdentity()
                if self.firmwareVersion is not None:
                    # Pin the adaptor so a later reconnect selects it directly
                    # by VID/PID + serial number instead of probing every
                    # adaptor again. Not the identity check itself (that was
                    # V? above); only an optimization for next time.
                    if candidateSerial is not None:
                        self.serialNumber = candidateSerial
                    return
                lastError = "{0} did not answer V? as a Fianium".format(candidatePath)
            except Exception as error:
                lastError = "{0}: {1}".format(candidatePath, error)
            if port.isOpen:
                port.close()
            self.port = None

        raise PhysicalDevice.UnableToInitialize(
            "No Fianium laser found on any FTDI adaptor ({0})".format(lastError))

    def _candidateAdaptors(self):
        """The (portPath, serialNumber) adaptors to probe.

        An explicit portPath is the only candidate. Otherwise every connected
        FTDI adaptor matching this device's VID/PID is a candidate, narrowed
        by serialNumber only when the caller actually supplied one
        (PhysicalDevice turns the default into ".*", which matches any).
        """
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

    def readIdentity(self):
        """Query V? and set firmwareVersion only if the reply looks like this
        firmware's version string (e.g. "Issue 5.17 20th February 2012").
        Leaves firmwareVersion None on any other reply, which is how
        doInitializeDevice tells a real Fianium from a wrong port."""
        try:
            version, = self.queryMatchingGroups("V?", r"(Issue \d+\.\d+.*)")
            self.firmwareVersion = version.strip()
        except CommunicationReadNoMatch:
            self.firmwareVersion = None

    def doShutdownDevice(self):
        if self.port is not None:
            self.port.close()
            self.port = None

    def queryString(self, query) -> str:
        """Free-form status text (alarms, control mode, heater status, ...)
        with no fixed reply format worth validating: we have, for instance,
        never seen this unit raise an alarm, so there is nothing to match A?
        against yet. flushFirst is required, not defensive: every reply on
        this console leaves its trailing "Command>" prompt unread (readString
        stops at the first '\\n', before the prompt), so without a flush the
        next query would read the previous prompt instead of its own reply."""
        return self.port.writeStringReadReply(
            query + self.commandTerminator, flushFirst=True).strip()

    def queryMatchingGroups(self, query, replyPattern) -> tuple:
        """Like queryString, but for a reply with a known structure: delegates
        to CommunicationPort.writeStringReadMatchingGroups instead of
        re-parsing a raw string by hand, so a reply that does not match
        replyPattern raises CommunicationReadNoMatch rather than returning
        None from an ad hoc re.search for the caller to crash on."""
        _, groups = self.port.writeStringReadMatchingGroups(
            query + self.commandTerminator, replyPattern, flushFirst=True)
        return groups

    # --- OnOffCapability hooks ---

    def doGetOnOffState(self) -> bool:
        pumaDrive, _ = self.amplifierDrive()
        return pumaDrive > 0 and self.preampPhotodiode() > self.seedDetectionThreshold

    def doTurnOn(self):
        self._refuseManualOnly("turnOn")

    def doTurnOff(self):
        self._refuseManualOnly("turnOff")

    def _refuseManualOnly(self, operation):
        mode = self.controlMode()
        raise FianiumManualInterventionRequired(
            "Cannot {0}() in software: control mode is {1!r}. Emission on this "
            "laser is gated by the physical 'Oscillator ON' knob and 'LASER' "
            "key on the chassis; this driver never writes M= or Q= (see "
            "FianiumManualInterventionRequired).".format(operation, mode))

    # --- Diagnostics: no Capability in hardwarelibrary.capabilities matches
    # these (alarms, temperature, running hours, raw pump drive, ...), so they
    # are plain public methods instead of capability-wrapped ones.

    def controlMode(self) -> str:
        return self.queryString("M?")

    def heaterStatus(self) -> str:
        return self.queryString("O?")

    def alarms(self) -> str:
        return self.queryString("A?")

    def runningHours(self) -> str:
        return self.queryString("W?")

    def backReflectionPhotodiode(self) -> int:
        value, = self.queryMatchingGroups("B?", r"Back reflection photodiode = (\d+)")
        return int(value)

    def preampPhotodiode(self) -> int:
        value, = self.queryMatchingGroups("P?", r"Preamplifier photodiode = (\d+)")
        return int(value)

    def amplifierDrive(self) -> tuple:
        """Raw amplifier driver reading from Q? ("Puma drive is X, DAC is Y"),
        as (pumaDrive, dac). Uncalibrated DAC/driver units (0-255 observed),
        not watts: there is no command on this console that reports absolute
        optical power, so PowerCapability is deliberately not implemented."""
        pumaDrive, dac = self.queryMatchingGroups(
            "Q?", r"Puma drive is (\d+), DAC is (\d+)")
        return int(pumaDrive), int(dac)

    # --- TemperatureCapability / PulsePickerCapability hooks ---

    def doGetTemperature(self) -> float:
        value, = self.queryMatchingGroups("T?", r"Temperature is (-?\d+\.?\d*) deg C")
        return float(value)

    def doGetPulsePickerFrequency(self) -> float:
        megahertz, = self.queryMatchingGroups("R?", r"Frequency = ([\d.]+) MHz")
        return float(megahertz) * 1e6

    def doGetStatusUserInfo(self) -> dict:
        pumaDrive, dac = self.amplifierDrive()
        return {
            "firmwareVersion": self.firmwareVersion,
            "temperature": self.temperature(),
            "alarms": self.alarms(),
            "controlMode": self.controlMode(),
            "pumaDrive": pumaDrive,
            "dac": dac,
            "preampPhotodiode": self.preampPhotodiode(),
            "backReflectionPhotodiode": self.backReflectionPhotodiode(),
            "isLaserOn": self.doGetOnOffState(),
        }


class DebugFianiumLaserDevice(FianiumLaserDevice):
    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF5
    usesGenericSerialConverter = False  # debug device has its own fake identity

    def __init__(self, serialNumber="debug"):
        super().__init__(portPath="debug", serialNumber=serialNumber)
        self.simulatedControlMode = "Pot controlled open loop mode"
        self.simulatedPumaDrive = 0
        self.simulatedPreamp = 10  # noise floor, laser off
        self.simulatedTemperature = 20.5
        self.simulatedAlarms = "No alarms"

    def doInitializeDevice(self):
        self.firmwareVersion = "Issue 5.17 20th February 2012"

    def doShutdownDevice(self):
        pass

    def queryString(self, query) -> str:
        return self._simulatedReply(query)

    def queryMatchingGroups(self, query, replyPattern) -> tuple:
        # No real port to delegate to, so this simulates what
        # writeStringReadMatchingGroups would do against the same reply
        # queryString would return for query.
        reply = self._simulatedReply(query)
        match = re.search(replyPattern, reply)
        if match is None:
            raise CommunicationReadNoMatch(
                "Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))
        return match.groups()

    def _simulatedReply(self, query) -> str:
        if query == "V?":
            return self.firmwareVersion
        elif query == "M?":
            return self.simulatedControlMode
        elif query == "O?":
            return "Laser Temperature ready"
        elif query == "T?":
            return "Temperature is {0:.1f} deg C".format(self.simulatedTemperature)
        elif query == "A?":
            return self.simulatedAlarms
        elif query == "W?":
            return "Time elapsed = 0 hours 0 minutes"
        elif query == "B?":
            return "Back reflection photodiode = 12"
        elif query == "P?":
            return "Preamplifier photodiode = {0}".format(self.simulatedPreamp)
        elif query == "Q?":
            return "Puma drive is {0}, DAC is {0}".format(self.simulatedPumaDrive)
        elif query == "R?":
            return "Frequency = 2.00 MHz"
        return "Command error"
