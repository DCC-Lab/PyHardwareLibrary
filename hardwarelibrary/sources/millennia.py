import time

from ..physicaldevice import PhysicalDevice
from ..communication.serialport import SerialPort
from .lasersourcedevice import LaserSourceDevice
from .capabilities import OnOffControl, ShutterControl, PowerControl


class MillenniaEv25Device(LaserSourceDevice, OnOffControl, ShutterControl, PowerControl):
    """Spectra-Physics Millennia eV CW DPSS pump laser (532 nm).

    Transport is the eV's back-panel USB port, which exposes a virtual COM
    port to the host (STM32 micro-controller). From pyserial's point of view
    it is a serial port at 115200 8-N-1, so the driver works whether the wire
    is native USB or, on older eV revisions, true RS-232 through an external
    USB-serial adapter.

    The eV speaks a compact ASCII protocol. Action commands (ON, OFF, SHT:1,
    SHT:0) are executed silently with no reply, while queries (?D, ?SHT) return
    a single value line terminated by <CR><LF>. Because actions return nothing,
    queryString flushes the input first to drop any stray bytes left behind by
    a previous action or by power-up chatter (the approach the savikhin-lab eV
    driver relies on).

    ON/OFF gate the pump diodes; the shutter is a separate electromechanical
    block in front of the output, so the laser can be on with the shutter
    closed. doGetOnOffState therefore reads the diode emission state (?D), not
    the shutter. This eV dialect is not the classic Millennia Pro/V one
    (SHUTTER:x, ?STB); see manuals/Spectra-Physics-Millennia-eV-Serial-Commands.md.
    """

    # The lab eV25s enumerates its back-panel USB port as a native STM32
    # USB-CDC device: VID 0x0483, PID 0x5740 (confirmed on the bench, firmware
    # SW214-00.004.096). doInitializeDevice discovers the port by this identity
    # when no portPath is given.
    #
    # Caveat: 0x0483:0x5740 is STMicroelectronics' *generic* STM32 Virtual COM
    # Port identity, shared by many unrelated STM32-based USB-CDC boards. On a
    # host that also has another STM32 CDC device, discovery could bind to the
    # wrong port; pin it with an explicit portPath (or narrow with a
    # serialNumber) in that case. A given portPath always wins over discovery.
    # To re-derive the identity on another unit:
    #
    #   system_profiler SPUSBDataType | grep -A 12 -i millennia
    #   .venv/bin/python -c "from serial.tools.list_ports import comports; \
    #     [print(p.device, hex(p.vid or 0), hex(p.pid or 0), p.serial_number) \
    #      for p in comports()]"

    classIdVendor = 0x0483   # STMicroelectronics
    classIdProduct = 0x5740  # STM32 Virtual COM Port (generic STM32 CDC identity)

    defaultBaudRate = 115200
    commandTerminator = "\r"  # the eV accepts <CR>, <LF>, or both
    minPower = 0.05  # documented eV/Pro-s lower bound
    maxPower = 25.0  # eV25s spec; override on subclass for eV5/10/15/20
    powerSetpointTolerance = 0.005  # W, finer than the eV's 0.01 W setpoint step
    # The eV does not ack action commands (ON/OFF, P:<f>), so the driver confirms
    # the ones that matter by reading the matching query back and retrying. It
    # also needs a moment to commit a command before the query reflects it (a
    # too-soon read returns the stale prior value) and refuses a setpoint change
    # while the output is still ramping. This is a set-and-forget pump laser, not
    # changed rapidly, so a generous settle costs nothing.
    settleDelay = 1.0  # seconds between an action command and its confirmation read
    confirmAttempts = 8  # write + confirm retries before giving up

    class UnableToConfirmSetpoint(Exception):
        pass

    class UnableToConfirmState(Exception):
        pass

    def __init__(self, portPath=None, serialNumber=None, idProduct=None, idVendor=None):
        super().__init__(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.portPath = portPath
        self.port = None
        self.idn = None
        self.manufacturer = None
        self.model = None
        self.firmwareVersion = None
        self.laserSerialNumber = None

    def doInitializeDevice(self):
        if self.portPath is not None:
            self.port = SerialPort(portPath=self.portPath)
        else:
            # Discover by the STM32 USB-CDC identity. serialNumber is a regex
            # (PhysicalDevice turns the default into ".*"); pass it only when it
            # actually narrows, so SerialPort.matchPorts stays on its vid/pid
            # path and never regex-matches against a possibly-None descriptor
            # serial.
            serialNumber = None if self.serialNumber in (None, ".*") else self.serialNumber
            self.port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct,
                                   serialNumber=serialNumber)
            if self.port.portPath is None:
                raise PhysicalDevice.UnableToInitialize(
                    "No Millennia eV found by USB identity {0:#06x}:{1:#06x}. "
                    "Pass an explicit portPath if several STM32 USB-CDC ports "
                    "are present.".format(self.idVendor, self.idProduct))
        try:
            self.port.open(baudRate=self.defaultBaudRate)
            self.readIdentity()
        except Exception as error:
            if self.port is not None and self.port.isOpen:
                self.port.close()
            # Preserve the underlying error (e.g. pyserial's "[Errno 16]
            # Resource busy") so callers can tell a busy port from a missing
            # one instead of seeing a bare, info-less UnableToInitialize.
            raise PhysicalDevice.UnableToInitialize(error) from error

    def readIdentity(self):
        # The eV identifies via the SCPI-style *IDN? query. The ?IDN form in
        # some Millennia docs is silently ignored by this firmware (it returns
        # nothing, the same way an out-of-range P: is dropped). The reply is
        # comma-separated as manufacturer, model, serial, firmware, e.g.
        #   Spectra_Physics,Millennia eV,3239,214-00.004.096/CD00000019
        # confirmed on the lab eV25s (firmware SW214-00.004.096, head S/N 3239).
        # Note serial precedes firmware here, the reverse of the classic
        # Millennia ?IDN ordering. Keep the raw string in self.idn for callers
        # that need exact provenance.
        self.idn = self.queryString("*IDN?")
        fields = [field.strip() for field in self.idn.split(",")]
        self.manufacturer = fields[0] if len(fields) > 0 else None
        self.model = fields[1] if len(fields) > 1 else None
        self.laserSerialNumber = fields[2] if len(fields) > 2 else None
        self.firmwareVersion = fields[3] if len(fields) > 3 else None

    def doShutdownDevice(self):
        if self.port is not None:
            self.port.close()
            self.port = None

    def writeCommand(self, command):
        self.port.writeString(command + self.commandTerminator)

    def queryString(self, query) -> str:
        with self.port.transactionLock:
            self.port.flush()
            self.port.writeString(query + self.commandTerminator)
            return self.port.readString().strip()

    def writeActionAndConfirm(self, command, query, expectedReply, description):
        # Like doSetPower, for an action command that has no ack: write, let the
        # eV commit it, confirm via the matching query, and retry; raise if it
        # never takes. NOTE: this confirm path for ON/OFF has not been exercised
        # against hardware (the diodes are intentionally not cycle-tested), and
        # the ?D emission flag's latency after ON/OFF -- a command latch vs the
        # several-second diode warm-up -- is unconfirmed. If ?D only asserts once
        # the laser is actually emitting, confirmAttempts/settleDelay will need to
        # span the warm-up; revisit once the laser can be cycled safely.
        reply = None
        for _ in range(self.confirmAttempts):
            self.writeCommand(command)
            time.sleep(self.settleDelay)
            reply = self.queryString(query)
            if not reply:
                return  # firmware does not answer the query; trust the write
            if reply == expectedReply:
                return
        raise self.UnableToConfirmState(
            "Millennia did not confirm {0} (last {1}={2!r})".format(
                description, query, reply))

    # OnOffControl hooks (the pump diodes)

    def doTurnOn(self):
        self.writeActionAndConfirm("ON", "?D", "1", "diodes on")

    def doTurnOff(self):
        self.writeActionAndConfirm("OFF", "?D", "0", "diodes off")

    def doGetOnOffState(self) -> bool:
        return self.queryString("?D") == "1"

    # ShutterControl hooks (the output-blocking shutter)

    def doOpenShutter(self):
        self.writeCommand("SHT:1")

    def doCloseShutter(self):
        self.writeCommand("SHT:0")

    def doGetShutterState(self) -> bool:
        return self.queryString("?SHT") == "1"

    # PowerControl hooks (output power in watts)

    def doSetPower(self, power: float):
        # The eV silently ignores out-of-range P: values, which would mask the
        # error downstream; refuse the call here so it fails loudly.
        if not (self.minPower <= power <= self.maxPower):
            raise ValueError(
                "power {0} W outside Millennia range [{1}, {2}] W".format(
                    power, self.minPower, self.maxPower))
        # The eV does not ack action commands, so a P: that does not take would
        # fail silently. Two things cause that: a too-soon ?PSET read returns the
        # stale prior setpoint (hence the settle), and the eV refuses a new
        # setpoint while the output is still ramping to the previous one. Write,
        # settle, confirm against the echoed setpoint, and retry; raise if it
        # never takes (e.g. called mid-ramp) rather than let the caller believe a
        # rejected setpoint was applied. Firmware that does not echo ?PSET returns
        # nothing: write once and trust it.
        command = "P:{0:.2f}".format(power)
        echoed = None
        for _ in range(self.confirmAttempts):
            self.writeCommand(command)
            time.sleep(self.settleDelay)
            echoed = self.queryString("?PSET")
            if not echoed:
                return
            if abs(float(echoed) - power) < self.powerSetpointTolerance:
                return
        raise self.UnableToConfirmSetpoint(
            "Millennia did not accept setpoint {0:.2f} W after {1} writes "
            "(last ?PSET={2!r})".format(power, self.confirmAttempts, echoed))

    def doGetPower(self) -> float:
        # ?P returns either a bare number ("4.90") or a number with the W unit
        # ("4.90 W") depending on firmware; take the first whitespace-separated
        # token.
        return float(self.queryString("?P").split()[0])

    # Status snapshot

    def doGetStatusUserInfo(self) -> dict:
        # Single-call snapshot for PhysicalDevice.startBackgroundStatusUpdates()
        # (posted as PhysicalDeviceNotification.status) and for GUI polling: the
        # output power plus the diode (emission) and shutter states. Without this
        # override the base returns None, so the monitoring loop posts nothing
        # useful for the eV.
        return {
            "power": self.doGetPower(),
            "isLaserOn": self.doGetOnOffState(),
            "isShutterOpen": self.doGetShutterState(),
        }


class DebugMillenniaEv25Device(MillenniaEv25Device):
    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF2
    settleDelay = 0  # the mock commits action commands instantly; no need to wait

    def __init__(self, serialNumber="debug"):
        super().__init__(portPath="debug", serialNumber=serialNumber)
        self.diodeIsOn = False
        self.shutterIsOpen = False
        self.outputPower = 0.0  # last-commanded output power in watts

    def doInitializeDevice(self):
        self.readIdentity()

    def doShutdownDevice(self):
        pass

    def writeCommand(self, command):
        if command == "ON":
            self.diodeIsOn = True
        elif command == "OFF":
            self.diodeIsOn = False
        elif command == "SHT:1":
            self.shutterIsOpen = True
        elif command == "SHT:0":
            self.shutterIsOpen = False
        elif command.startswith("P:"):
            self.outputPower = float(command[len("P:"):])

    def queryString(self, query) -> str:
        if query == "?D":
            return "1" if self.diodeIsOn else "0"
        elif query == "?SHT":
            return "1" if self.shutterIsOpen else "0"
        elif query == "?P" or query == "?PSET":
            return "{0:.2f}".format(self.outputPower)
        elif query == "*IDN?":
            # Mirrors the lab eV25s *IDN? reply verbatim (manufacturer, model,
            # head S/N 3239, firmware SW214-00.004.096) so readIdentity
            # exercises the real wire format and field ordering.
            return "Spectra_Physics,Millennia eV,3239,214-00.004.096/CD00000019"
        return "0"


# Short alias for the currently-implemented Millennia variant. The eV25s is
# the only Millennia driver in the library today, so MillenniaDevice points
# at it for convenience; once sibling drivers land for other variants
# (Millennia X with the classic ASCII dialect, or another eV-series at a
# different transport), reconsider this alias and migrate callers to the
# explicit class.
MillenniaDevice = MillenniaEv25Device
DebugMillenniaDevice = DebugMillenniaEv25Device
