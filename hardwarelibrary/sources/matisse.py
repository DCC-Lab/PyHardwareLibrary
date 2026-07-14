import time

from ..physicaldevice import PhysicalDevice
from ..communication.labviewtcpport import LabviewTCPPort
from ..communication.communicationport import CommunicationReadError
from ..communication.debugport import DebugPort
from .capabilities import WavelengthCapability


class MatisseCommanderError(Exception):
    pass


class MatisseDevice(PhysicalDevice, WavelengthCapability):
    """Sirah Matisse tunable laser, controlled over the Matisse Commander server.

    Wavelength tuning is a hierarchy of intracavity elements, coarse to fine:
    the birefringent filter (BiFi) selects a coarse band, the thin etalon
    narrows it, and the piezo etalon, slow piezo and fast piezo provide
    successively finer, faster control; a scan engine sweeps the fine elements.
    Each element is exposed below with its own get/set/motion/lock methods. The
    high-level WavelengthCapability interface (setWavelength/wavelength) drives the
    BiFi, which is the coarse wavelength selector; use the etalon and piezo
    methods for fine tuning.

    The transport is a LabviewTCPPort (Matisse Commander is a LabVIEW TCP
    server, so the wire framing is LabVIEW's length-prefixed strings). The
    Matisse reply grammar lives here, not in the transport: a query reply
    echoes the command behind a ':' (':MOTBI:WL: 760.0'), a set replies 'OK',
    and a failure replies '!ERROR <code>,<message>'. query and sendSetting
    express this grammar as the port's replyPattern/errorPattern, mapping a
    matched error reply to MatisseCommanderError. Commands follow the Sirah
    Matisse Programmer's Guide v2.4.8 (short forms).
    """

    classIdVendor = 0x17E7   # Sirah; used for identity only (the link is TCP, not USB)
    classIdProduct = 0x0102
    runningTokens = ("RUN", "RU", "TRUE")
    movingStatusBit = 1 << 8
    closeSettleDelay = 0.3
    valuePattern = r"^:\S*\s+(.*)$"   # a query reply ':CMD: value' -> captures value
    errorPattern = r"!ERROR\s*(.*)"   # a failure reply '!ERROR code,message'

    def __init__(self, host, networkPort=30000, serialNumber="*", wavelengthRange=(700.0, 1000.0)):
        super().__init__(serialNumber=serialNumber, idProduct=None, idVendor=None)
        self.host = host
        self.networkPort = networkPort
        self.configuredWavelengthRange = wavelengthRange  # set by the installed optics, not queryable
        self.idn = None

    def doInitializeDevice(self):
        self.port = LabviewTCPPort(self.host, self.networkPort)
        self.port.open()
        self.idn = self.query("IDN?")

    def doShutdownDevice(self):
        # Matisse Commander frees its single client slot only on receiving this
        # server command; send it before PhysicalDevice.shutdownDevice closes
        # the socket, otherwise the orphaned slot refuses the next client.
        if self.port is not None:
            try:
                self.port.writeString("Close_Network_Connection")
                time.sleep(self.closeSettleDelay)
            except OSError:
                pass

    def query(self, command) -> str:
        # A query reply echoes the command behind a ':' (':MOTBI:WL: 760.0');
        # valuePattern captures what follows. A '!ERROR ...' reply matches
        # errorPattern, which the port surfaces as CommunicationReadError
        # carrying the error text; map it to the device-level error.
        try:
            _, value = self.port.writeStringReadFirstMatchingGroup(
                command, replyPattern=self.valuePattern, errorPattern=self.errorPattern)
        except CommunicationReadError as error:
            raise MatisseCommanderError(error.groups[0])
        return value

    def sendSetting(self, command):
        # A set replies 'OK', which must be consumed to stay framed-in-sync; a
        # '!ERROR ...' reply becomes a MatisseCommanderError, as for query.
        try:
            self.port.writeStringExpectMatchingString(
                command, replyPattern="OK", errorPattern=self.errorPattern)
        except CommunicationReadError as error:
            raise MatisseCommanderError(error.groups[0])

    def lockIsRunning(self, command) -> bool:
        return self.query(command).strip().upper() in self.runningTokens

    def resonatorPower(self) -> float:
        return float(self.query("DPOW:DC?"))

    # Birefringent filter (MOTBI) - coarse wavelength selector

    def bifiWavelength(self) -> float:
        return float(self.query("MOTBI:WL?"))

    def setBifiWavelength(self, wavelength, wait=True, timeout=30.0):
        self.sendSetting("MOTBI:WL {0:.4f}".format(wavelength))
        if wait:
            self.waitForBifi(timeout=timeout)

    def bifiPosition(self) -> int:
        return int(self.query("MOTBI:POS?"))

    def setBifiPosition(self, position, wait=True, timeout=30.0):
        self.sendSetting("MOTBI:POS {0:d}".format(int(position)))
        if wait:
            self.waitForBifi(timeout=timeout)

    def bifiMaximumPosition(self) -> int:
        return int(self.query("MOTBI:MAX?"))

    def bifiStatusWord(self) -> int:
        return int(self.query("MOTBI:STA?"))

    def bifiIsMoving(self) -> bool:
        return bool(self.bifiStatusWord() & self.movingStatusBit)

    def bifiMotorFrequency(self) -> int:
        return int(self.query("MOTBI:FREQ?"))

    def setBifiMotorFrequency(self, frequency):
        self.sendSetting("MOTBI:FREQ {0:d}".format(int(frequency)))

    def homeBifi(self, wait=True, timeout=30.0):
        self.sendSetting("MOTBI:HOME")
        if wait:
            self.waitForBifi(timeout=timeout)

    def haltBifi(self):
        self.sendSetting("MOTBI:HALT")

    def clearBifiErrors(self):
        self.sendSetting("MOTBI:CL")

    def waitForBifi(self, timeout=30.0):
        self.waitWhileMoving(self.bifiIsMoving, timeout)

    # Thin etalon motor (MOTTE) - medium tuning

    def thinEtalonPosition(self) -> int:
        return int(self.query("MOTTE:POS?"))

    def setThinEtalonPosition(self, position, wait=True, timeout=30.0):
        self.sendSetting("MOTTE:POS {0:d}".format(int(position)))
        if wait:
            self.waitForThinEtalon(timeout=timeout)

    def thinEtalonMaximumPosition(self) -> int:
        return int(self.query("MOTTE:MAX?"))

    def thinEtalonStatusWord(self) -> int:
        return int(self.query("MOTTE:STA?"))

    def thinEtalonIsMoving(self) -> bool:
        return bool(self.thinEtalonStatusWord() & self.movingStatusBit)

    def thinEtalonMotorFrequency(self) -> int:
        return int(self.query("MOTTE:FREQ?"))

    def setThinEtalonMotorFrequency(self, frequency):
        self.sendSetting("MOTTE:FREQ {0:d}".format(int(frequency)))

    def homeThinEtalon(self, wait=True, timeout=30.0):
        self.sendSetting("MOTTE:HOME")
        if wait:
            self.waitForThinEtalon(timeout=timeout)

    def haltThinEtalon(self):
        self.sendSetting("MOTTE:HALT")

    def clearThinEtalonErrors(self):
        self.sendSetting("MOTTE:CL")

    def waitForThinEtalon(self, timeout=30.0):
        self.waitWhileMoving(self.thinEtalonIsMoving, timeout)

    # Thin etalon lock (TE)

    def thinEtalonReflexPower(self) -> float:
        return float(self.query("TE:DC?"))

    def thinEtalonErrorSignal(self) -> float:
        try:
            return float(self.query("TE:CNTRERR?"))
        except MatisseCommanderError:
            # Firmware before ~1.6 (the lab unit runs 1.20) lacks TE:CNTRERR, so
            # reconstruct it the way pylablib does: setpoint minus the reflex /
            # resonator power ratio.
            return self.thinEtalonSetpoint() - self.thinEtalonReflexPower() / self.resonatorPower()

    def thinEtalonLockIsOn(self) -> bool:
        return self.lockIsRunning("TE:CNTRSTA?")

    def setThinEtalonLock(self, on=True):
        self.sendSetting("TE:CNTRSTA {0}".format("RUN" if on else "STOP"))

    def thinEtalonSetpoint(self) -> float:
        return float(self.query("TE:CNTRSP?"))

    def setThinEtalonSetpoint(self, setpoint):
        self.sendSetting("TE:CNTRSP {0:.6f}".format(setpoint))

    def thinEtalonProportionalGain(self) -> float:
        return float(self.query("TE:CNTRPROP?"))

    def setThinEtalonProportionalGain(self, gain):
        self.sendSetting("TE:CNTRPROP {0:.6f}".format(gain))

    def thinEtalonIntegralGain(self) -> float:
        return float(self.query("TE:CNTRINT?"))

    def setThinEtalonIntegralGain(self, gain):
        self.sendSetting("TE:CNTRINT {0:.6f}".format(gain))

    def thinEtalonAveraging(self) -> int:
        return int(self.query("TE:CNTRAVG?"))

    def setThinEtalonAveraging(self, averaging):
        self.sendSetting("TE:CNTRAVG {0:d}".format(int(averaging)))

    # Piezo etalon (PZETL) and its feed-forward (FEF) - fine tuning

    def piezoEtalonBaseline(self) -> float:
        return float(self.query("PZETL:BASE?"))

    def setPiezoEtalonBaseline(self, baseline):
        self.sendSetting("PZETL:BASE {0:.6f}".format(baseline))

    def piezoEtalonAmplitude(self) -> float:
        return float(self.query("PZETL:AMP?"))

    def setPiezoEtalonAmplitude(self, amplitude):
        self.sendSetting("PZETL:AMP {0:.6f}".format(amplitude))

    def piezoEtalonOversampling(self) -> int:
        return int(self.query("PZETL:OVER?"))

    def setPiezoEtalonOversampling(self, oversampling):
        self.sendSetting("PZETL:OVER {0:d}".format(int(oversampling)))

    def piezoEtalonLockIsOn(self) -> bool:
        return self.lockIsRunning("PZETL:CNTRSTA?")

    def setPiezoEtalonLock(self, on=True):
        self.sendSetting("PZETL:CNTRSTA {0}".format("RUN" if on else "STOP"))

    def piezoEtalonProportionalGain(self) -> float:
        return float(self.query("PZETL:CNTRPROP?"))

    def setPiezoEtalonProportionalGain(self, gain):
        self.sendSetting("PZETL:CNTRPROP {0:.6f}".format(gain))

    def piezoEtalonAveraging(self) -> int:
        return int(self.query("PZETL:CNTRAVG?"))

    def setPiezoEtalonAveraging(self, averaging):
        self.sendSetting("PZETL:CNTRAVG {0:d}".format(int(averaging)))

    def piezoEtalonPhase(self) -> int:
        return int(self.query("PZETL:CNTRPHSF?"))

    def setPiezoEtalonPhase(self, phase):
        self.sendSetting("PZETL:CNTRPHSF {0:d}".format(int(phase)))

    def piezoEtalonFeedforwardAmplitude(self) -> float:
        return float(self.query("FEF:AMP?"))

    def setPiezoEtalonFeedforwardAmplitude(self, amplitude):
        self.sendSetting("FEF:AMP {0:.6f}".format(amplitude))

    def piezoEtalonFeedforwardPhase(self) -> int:
        return int(self.query("FEF:PHSF?"))

    def setPiezoEtalonFeedforwardPhase(self, phase):
        self.sendSetting("FEF:PHSF {0:d}".format(int(phase)))

    # Slow piezo (SPZT) - cavity-length fine tuning

    def slowPiezoValue(self) -> float:
        return float(self.query("SPZT:NOW?"))

    def setSlowPiezoValue(self, value):
        self.sendSetting("SPZT:NOW {0:.6f}".format(value))

    def slowPiezoLockIsOn(self) -> bool:
        return self.lockIsRunning("SPZT:CNTRSTA?")

    def setSlowPiezoLock(self, on=True):
        self.sendSetting("SPZT:CNTRSTA {0}".format("RUN" if on else "STOP"))

    def slowPiezoSetpoint(self) -> float:
        return float(self.query("SPZT:CNTRSP?"))

    def setSlowPiezoSetpoint(self, setpoint):
        self.sendSetting("SPZT:CNTRSP {0:.6f}".format(setpoint))

    def slowPiezoProportionalGain(self) -> float:
        return float(self.query("SPZT:LPROP?"))

    def setSlowPiezoProportionalGain(self, gain):
        self.sendSetting("SPZT:LPROP {0:.6f}".format(gain))

    def slowPiezoIntegralGain(self) -> float:
        return float(self.query("SPZT:LINT?"))

    def setSlowPiezoIntegralGain(self, gain):
        self.sendSetting("SPZT:LINT {0:.6f}".format(gain))

    def slowPiezoFreerunningGain(self) -> float:
        return float(self.query("SPZT:FRSP?"))

    def setSlowPiezoFreerunningGain(self, gain):
        self.sendSetting("SPZT:FRSP {0:.6f}".format(gain))

    # Fast piezo (FPZT) - fastest fine tuning

    def fastPiezoValue(self) -> float:
        return float(self.query("FPZT:NOW?"))

    def setFastPiezoValue(self, value):
        self.sendSetting("FPZT:NOW {0:.6f}".format(value))

    def fastPiezoInput(self) -> float:
        return float(self.query("FPZT:INP?"))

    def fastPiezoIsLocked(self) -> bool:
        return self.query("FPZT:LOCK?").strip().upper() in ("TRUE", "1")

    def fastPiezoLockIsOn(self) -> bool:
        return self.lockIsRunning("FPZT:CNTRSTA?")

    def setFastPiezoLock(self, on=True):
        self.sendSetting("FPZT:CNTRSTA {0}".format("RUN" if on else "STOP"))

    def fastPiezoSetpoint(self) -> float:
        return float(self.query("FPZT:CNTRSP?"))

    def setFastPiezoSetpoint(self, setpoint):
        self.sendSetting("FPZT:CNTRSP {0:.6f}".format(setpoint))

    def fastPiezoLockpoint(self) -> float:
        return float(self.query("FPZT:LKP?"))

    def setFastPiezoLockpoint(self, lockpoint):
        self.sendSetting("FPZT:LKP {0:.6f}".format(lockpoint))

    def fastPiezoIntegralGain(self) -> float:
        return float(self.query("FPZT:CNTRINT?"))

    def setFastPiezoIntegralGain(self, gain):
        self.sendSetting("FPZT:CNTRINT {0:.6f}".format(gain))

    # Scan engine (SCAN) - sweeps the selected fine element

    def scanIsRunning(self) -> bool:
        return self.lockIsRunning("SCAN:STA?")

    def setScanRunning(self, running=True):
        self.sendSetting("SCAN:STA {0}".format("RUN" if running else "STOP"))

    def scanValue(self) -> float:
        return float(self.query("SCAN:NOW?"))

    def setScanValue(self, value):
        self.sendSetting("SCAN:NOW {0:.6f}".format(value))

    def scanDevice(self) -> int:
        return int(self.query("SCAN:DEV?"))

    def setScanDevice(self, device):
        self.sendSetting("SCAN:DEV {0:d}".format(int(device)))

    def scanMode(self) -> int:
        return int(self.query("SCAN:MODE?"))

    def setScanMode(self, mode):
        self.sendSetting("SCAN:MODE {0:d}".format(int(mode)))

    def scanLowerLimit(self) -> float:
        return float(self.query("SCAN:LLM?"))

    def setScanLowerLimit(self, limit):
        self.sendSetting("SCAN:LLM {0:.6f}".format(limit))

    def scanUpperLimit(self) -> float:
        return float(self.query("SCAN:ULM?"))

    def setScanUpperLimit(self, limit):
        self.sendSetting("SCAN:ULM {0:.6f}".format(limit))

    def scanRisingSpeed(self) -> float:
        return float(self.query("SCAN:RSPD?"))

    def setScanRisingSpeed(self, speed):
        self.sendSetting("SCAN:RSPD {0:.6f}".format(speed))

    def scanFallingSpeed(self) -> float:
        return float(self.query("SCAN:FSPD?"))

    def setScanFallingSpeed(self, speed):
        self.sendSetting("SCAN:FSPD {0:.6f}".format(speed))

    # WavelengthCapability hooks (the BiFi is the coarse wavelength selector)

    def doGetWavelength(self) -> float:
        return self.bifiWavelength()

    def doSetWavelength(self, wavelength):
        self.setBifiWavelength(wavelength)

    def doGetWavelengthRange(self) -> tuple:
        return self.configuredWavelengthRange

    def waitWhileMoving(self, isMoving, timeout):
        deadline = time.time() + timeout
        while isMoving():
            if time.time() > deadline:
                raise MatisseDevice.MotionTimeout("Element still moving after {0}s".format(timeout))
            time.sleep(0.05)

    class MotionTimeout(Exception):
        pass


class DebugMatissePort(DebugPort):
    """In-process stand-in for Matisse Commander: answers queries from a
    register dict and emits the Matisse reply grammar, so DebugMatisseDevice
    runs the exact same port code path as the real device instead of stubbing
    out query/sendSetting. The register dict is shared with the device, so
    tests can poke it directly (e.g. force a moving status word)."""

    def __init__(self, registers):
        super().__init__()
        self.registers = registers

    def processInputBuffers(self, endPointIndex):
        inputBytes = self.inputBuffers[endPointIndex]
        if len(inputBytes) == 0:
            return
        command = inputBytes.decode("utf-8").strip()
        self.inputBuffers[endPointIndex] = bytearray()
        reply = self.replyFor(command)
        if reply is not None:
            self.writeToOutputBuffer(bytearray(reply + "\n", "utf-8"), endPointIndex)

    def replyFor(self, command):
        if command == "Close_Network_Connection":
            return None  # server-only command, no device reply
        if command == "IDN?":
            return ':IDN: "Matisse Debug, S/N:00-00-00, Firmware:debug"'
        if command == "TE:CNTRERR?":
            return '!ERROR 1,"general syntax error"'  # absent on fw 1.20, like the lab unit
        if command.startswith("BAD"):
            return '!ERROR 1,"general syntax error"'
        if command.endswith("?"):
            return ":{0}: {1}".format(command[:-1], self.registers.get(command[:-1], "0"))
        parts = command.split(maxsplit=1)
        if len(parts) == 2:
            self.registers[parts[0]] = parts[1]
        elif parts[0].endswith(("HOME", "HALT", "CL")):
            self.registers[parts[0].rsplit(":", 1)[0] + ":STA"] = "2"  # land idle after a motion action
        return "OK"


class DebugMatisseDevice(MatisseDevice):
    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF1

    def __init__(self, serialNumber="debug", wavelengthRange=(700.0, 1000.0)):
        super().__init__(host="debug", networkPort=0, serialNumber=serialNumber, wavelengthRange=wavelengthRange)
        self.registers = {
            "MOTBI:WL": "760.0", "MOTBI:POS": "100000", "MOTBI:MAX": "1000000",
            "MOTBI:STA": "2", "MOTBI:FREQ": "10000",
            "MOTTE:POS": "5000", "MOTTE:MAX": "60000", "MOTTE:STA": "2", "MOTTE:FREQ": "8000",
            "DPOW:DC": "0.45",
            "TE:DC": "0.42", "TE:CNTRSTA": "STOP",
            "TE:CNTRSP": "0.5", "TE:CNTRPROP": "1.0", "TE:CNTRINT": "0.1", "TE:CNTRAVG": "16",
            "PZETL:BASE": "0.0", "PZETL:AMP": "0.5", "PZETL:OVER": "16",
            "PZETL:CNTRSTA": "STOP", "PZETL:CNTRPROP": "1.0", "PZETL:CNTRAVG": "8", "PZETL:CNTRPHSF": "0",
            "FEF:AMP": "0.0", "FEF:PHSF": "0",
            "SPZT:NOW": "0.5", "SPZT:CNTRSTA": "STOP", "SPZT:CNTRSP": "0.0",
            "SPZT:LPROP": "1.0", "SPZT:LINT": "0.1", "SPZT:FRSP": "0.0",
            "FPZT:NOW": "0.5", "FPZT:INP": "0.5", "FPZT:LOCK": "FALSE", "FPZT:CNTRSTA": "STOP",
            "FPZT:CNTRSP": "0.0", "FPZT:LKP": "0.5", "FPZT:CNTRINT": "0.1",
            "SCAN:STA": "STOP", "SCAN:NOW": "0.0", "SCAN:DEV": "0", "SCAN:MODE": "0",
            "SCAN:LLM": "0.0", "SCAN:ULM": "1.0", "SCAN:RSPD": "0.1", "SCAN:FSPD": "0.1",
        }
        self.closeSettleDelay = 0  # no real socket to let go of

    def doInitializeDevice(self):
        self.port = DebugMatissePort(self.registers)
        self.port.open()
        self.idn = self.query("IDN?")
