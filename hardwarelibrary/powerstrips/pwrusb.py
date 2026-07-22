"""PwrUSB / PowerUSB controllable power strip (USB HID, 04d8:003f).

The strip enumerates as a Microchip HID device ("Simple HID Device Demo") and
carries one always-on outlet plus three switchable outlets. It is driven with a
single-byte HID report protocol: write one command byte; for query commands,
read the reply back.

Command bytes (outlets are 1-based here to match the physical labels):

    Action        Outlet 1  Outlet 2  Outlet 3
    On            0x41      0x43      0x45
    Off           0x42      0x44      0x50
    Default on    0x4E      0x47      0x4F     (state after mains power returns)
    Default off   0x46      0x51      0x48

    Query         Byte  Reply
    Device type   0xAA  1 byte  (1=Basic 2=Digital IO 3=Watchdog 4=Smart)
    Current       0xB1  2 bytes big-endian, milliamps
    Charge        0xB2  4 bytes big-endian, milliamp-minutes
    Reset charge  0xB3  none

Live outlet-state readback is unreliable on this hardware (a documented firmware
quirk: the read tends to return only the last port read), so the driver caches
each outlet's state as it is written and reports the cache.

The driver talks to the device through a HIDPort (hidapi/IOKit). HID is required
because the OS claims the interface: on macOS neither SerialPort (no /dev node)
nor USBPort/libusb can open it. Install the optional 'pwrusb' extra for hidapi.
The single-byte protocol above was reverse-engineered publicly; it was cross-
checked against aarossig/pwrusbctl (Apache-2.0, https://github.com/aarossig/pwrusbctl)
and pwrusb.com. The implementation here is our own.
"""

from hardwarelibrary.communication.hidport import HIDPort
from hardwarelibrary.communication.debugport import DebugPort
from hardwarelibrary.powerstrips.powerstripdevice import PowerStripDevice
from hardwarelibrary.capabilities import (
    OutletSwitchingCapability, DefaultOutletCapability, CurrentMeteringCapability,
)


class PwrUSBDevice(PowerStripDevice, OutletSwitchingCapability,
                   DefaultOutletCapability, CurrentMeteringCapability):
    classIdVendor = 0x04d8
    classIdProduct = 0x003f

    outletCommands = {
        "on":         [0x41, 0x43, 0x45],
        "off":        [0x42, 0x44, 0x50],
        "defaultOn":  [0x4E, 0x47, 0x4F],
        "defaultOff": [0x46, 0x51, 0x48],
    }
    getDeviceTypeCommand = 0xAA
    getCurrentCommand = 0xB1
    getChargeCommand = 0xB2
    resetChargeCommand = 0xB3

    deviceTypes = {1: "Basic", 2: "Digital IO", 3: "Watchdog", 4: "Smart"}

    switchableOutletCount = 3

    def __init__(self, serialNumber: str = None, idProduct: int = None,
                 idVendor: int = None, portPath: str = None):
        self.portPath = portPath
        self._outletStateCache = [False] * self.switchableOutletCount
        super().__init__(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.port = None

    def doInitializeDevice(self):
        # Let the underlying exception propagate unwrapped: PhysicalDevice.
        # initializeDevice wraps it once in UnableToInitialize, so callers can
        # read the true cause (e.g. an OSError from hidapi) from its args.
        try:
            if self.portPath == "debug":
                self.port = DebugPwrUSBPort()
            else:
                self.port = HIDPort(idVendor=self.idVendor, idProduct=self.idProduct,
                                    serialNumber=self.serialNumber)
            self.port.open()

            self._outletStateCache = [False] * self.switchableOutletCount
        except Exception:
            if self.port is not None and self.port.isOpen:
                self.port.close()
            self.port = None
            raise

    def doShutdownDevice(self):
        if self.port is not None:
            self.port.close()
        self.port = None

    def _validateOutlet(self, outlet: int):
        if outlet not in range(1, self.switchableOutletCount + 1):
            raise ValueError("Outlet must be 1..{0}, got {1}".format(
                self.switchableOutletCount, outlet))

    def deviceType(self) -> str:
        # flush() first so the reply is read from a clean buffer: a report can be
        # longer than the bytes we need, leaving a remainder buffered from the
        # previous query.
        self.port.flush()
        self.port.writeData(bytearray([self.getDeviceTypeCommand]))
        reply = self.port.readData(length=1)
        return self.deviceTypes.get(reply[0], "Unknown")

    def doGetOutletCount(self) -> int:
        return self.switchableOutletCount

    def doSetOutletState(self, outlet: int, isOn: bool):
        self._validateOutlet(outlet)
        key = "on" if isOn else "off"
        self.port.writeData(bytearray([self.outletCommands[key][outlet - 1]]))
        self._outletStateCache[outlet - 1] = bool(isOn)

    def doGetOutletState(self, outlet: int) -> bool:
        self._validateOutlet(outlet)
        return self._outletStateCache[outlet - 1]

    def doSetOutletDefaultState(self, outlet: int, isOn: bool):
        self._validateOutlet(outlet)
        key = "defaultOn" if isOn else "defaultOff"
        self.port.writeData(bytearray([self.outletCommands[key][outlet - 1]]))

    def doGetCurrent(self) -> float:
        self.port.flush()
        self.port.writeData(bytearray([self.getCurrentCommand]))
        reply = self.port.readData(length=2)
        milliamps = (reply[0] << 8) | reply[1]
        return milliamps / 1000.0

    def doGetAccumulatedCharge(self) -> float:
        self.port.flush()
        self.port.writeData(bytearray([self.getChargeCommand]))
        reply = self.port.readData(length=4)
        milliampMinutes = (reply[0] << 24) | (reply[1] << 16) | (reply[2] << 8) | reply[3]
        return milliampMinutes / 60000.0

    def doResetAccumulatedCharge(self):
        self.port.writeData(bytearray([self.resetChargeCommand]))


class DebugPwrUSBPort(DebugPort):
    """Mock port that decodes PwrUSBDevice command bytes and answers queries.

    It interprets the same command bytes the real strip does (so the driver's
    encoding is exercised end to end) and keeps in-memory outlet/default/meter
    state that tests can inspect.
    """

    def __init__(self):
        super().__init__()
        self.outletStates = [False] * PwrUSBDevice.switchableOutletCount
        self.defaultStates = [False] * PwrUSBDevice.switchableOutletCount
        self.currentMilliamps = 250
        self.chargeMilliampMinutes = 0
        self.deviceTypeCode = 4  # Smart: the metering-capable model

    def processInputBuffers(self, endPointIndex):
        inputBytes = self.inputBuffers[endPointIndex]
        if len(inputBytes) == 0:
            return

        byte = inputBytes[0]
        self.inputBuffers[endPointIndex] = bytearray()

        commands = PwrUSBDevice.outletCommands
        for index in range(PwrUSBDevice.switchableOutletCount):
            if byte == commands["on"][index]:
                self.outletStates[index] = True
                return
            if byte == commands["off"][index]:
                self.outletStates[index] = False
                return
            if byte == commands["defaultOn"][index]:
                self.defaultStates[index] = True
                return
            if byte == commands["defaultOff"][index]:
                self.defaultStates[index] = False
                return

        if byte == PwrUSBDevice.getDeviceTypeCommand:
            self.writeToOutputBuffer(bytearray([self.deviceTypeCode]), endPointIndex)
        elif byte == PwrUSBDevice.getCurrentCommand:
            value = self.currentMilliamps
            self.writeToOutputBuffer(bytearray([(value >> 8) & 0xFF, value & 0xFF]), endPointIndex)
        elif byte == PwrUSBDevice.getChargeCommand:
            value = self.chargeMilliampMinutes
            self.writeToOutputBuffer(bytearray([
                (value >> 24) & 0xFF, (value >> 16) & 0xFF,
                (value >> 8) & 0xFF, value & 0xFF]), endPointIndex)
        elif byte == PwrUSBDevice.resetChargeCommand:
            self.chargeMilliampMinutes = 0
        else:
            print("Unrecognized PwrUSB command byte: 0x{0:02x}".format(byte))


class DebugPwrUSBDevice(PwrUSBDevice):
    """Hardware-free PwrUSB strip for tests, backed by DebugPwrUSBPort."""

    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF9

    def __init__(self, serialNumber: str = "debug"):
        super().__init__(serialNumber=serialNumber,
                         idProduct=self.classIdProduct, idVendor=self.classIdVendor,
                         portPath="debug")
