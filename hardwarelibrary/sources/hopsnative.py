"""HOPSNativeInterface: the HOPS transport in pure Python over pyftdi I2C.

Implements the transport-agnostic HOPSInterface (see verdig.py) by driving the
HOPS supply's I2C bus directly through the FT2232 with pyftdi -- no CohrHOPS.dll,
no Windows. Reverse-engineered from sniffed I2C traffic (see
manuals/Coherent-HOPS-3-I2C-Wire-Protocol.md and Coherent-HOPS-3-I2C-Circuit.svg):

  - EEPROM 0x52 (2-byte pointer 0x01XX): identity/calibration (head type 0x00,
    head ID 0x10, board rev 0x60).
  - ADC 0x48: power at reg 0xE4, main temperature at reg 0x94 (2 bytes, BE).
  - I/O expander 0x25 (PCA9555-style): input port 0x00, output 0x02, config 0x06;
    bit0 shutter (1=open), bit3 remote (active-low, 0=on), bit5 emission enable.
  - DAC 0x29 reg 0xA0: 16-bit power setpoint.

Gaps (not yet reverse-engineered), so these raise HOPSInterface.NotSupported /
NotCalibrated: the full ?FF fault/interlock decode, and the ADC power-read scale
(only 0 counts = 0 W is known). Main-temperature uses a two-point cal valid
~32-40 C. On Ventura pyftdi claims the FT2232 without unloading Apple's VCP
driver; run with libusb reachable.
"""

import struct

from .verdig import HOPSInterface


class HOPSNativeI2C:
    """Register-level access to the HOPS I2C devices over a pyftdi-style bus.

    The bus exposes get_port(address) with .exchange(out, readlen) (read: write
    pointer then read) and .write(out) (write only). HOPSNativeI2C.open() builds
    the real pyftdi bus; tests inject a mock with the same interface.
    """

    EEPROM = 0x52
    EEPROM_PAGE = 0x01
    ADC = 0x48
    GPIO = 0x25
    DAC = 0x29
    GPIO_IN = 0x00
    GPIO_OUT = 0x02
    GPIO_CFG = 0x06

    def __init__(self, bus):
        self.bus = bus

    @classmethod
    def open(cls, url, frequency=10000):
        from pyftdi.ftdi import Ftdi
        from pyftdi.i2c import I2cController
        try:
            Ftdi.add_custom_product(0x0403, 0x6010, "HOPS")
        except Exception:
            pass
        controller = I2cController()
        controller.force_clock_mode(True)   # FT2232C/D has no 3-phase clock
        controller.configure(url, frequency=frequency)
        return cls(controller)

    def close(self):
        closer = getattr(self.bus, "close", None)
        if closer is not None:
            closer()

    def readEepromByte(self, register) -> int:
        return self.bus.get_port(self.EEPROM).exchange(
            [self.EEPROM_PAGE, register & 0xFF], 1)[0]

    def readEepromString(self, base, maxLength=32) -> str:
        out = bytearray()
        for offset in range(maxLength):
            byte = self.readEepromByte(base + offset)
            if byte == 0:
                break
            out.append(byte)
        return out.decode("ascii", "replace")

    def readEepromFloat(self, base) -> float:
        return struct.unpack(">f", bytes(self.readEepromByte(base + i) for i in range(4)))[0]

    def readAdc(self, register) -> int:
        data = self.bus.get_port(self.ADC).exchange([register], 2)
        return (data[0] << 8) | data[1]

    def readGpioBit(self, bit) -> int:
        port = self.bus.get_port(self.GPIO).exchange([self.GPIO_IN], 1)[0]
        return (port >> bit) & 0x01

    def writeGpioBit(self, bit, value):
        # Read-modify-write: make the pin an output (0 in config) and drive it,
        # leaving other bits untouched. Writes use write() -- pyftdi rejects
        # exchange(out, readlen=0) with "Nothing to read".
        gpio = self.bus.get_port(self.GPIO)
        config = gpio.exchange([self.GPIO_CFG], 1)[0] & ~(1 << bit)
        gpio.write([self.GPIO_CFG, config])
        output = gpio.exchange([self.GPIO_OUT], 1)[0]
        output = (output | (1 << bit)) if value else (output & ~(1 << bit))
        gpio.write([self.GPIO_OUT, output])

    def writeDac(self, register, code):
        code &= 0xFFFF
        self.bus.get_port(self.DAC).write([register, (code >> 8) & 0xFF, code & 0xFF])


class HOPSNativeInterface(HOPSInterface):
    """HOPS transport over native pyftdi I2C (no DLL)."""

    name = "native"
    defaultUrl = "ftdi://ftdi:0x6010:FTV5L9CA/1"

    HEAD_TYPE_REG = 0x00
    HEAD_ID_REG = 0x10
    POWER_REG = 0xE4
    TMAIN_REG = 0x94
    SHUTTER_BIT = 0
    REMOTE_BIT = 3       # active-low
    ENABLE_BIT = 5
    DAC_POWER_REG = 0xA0
    dacCountsPerWatt = 102.0   # provisional (PCMD=0.5 W -> 0x0033), refine later

    # Main-temperature two-point cal (NTC-like): raw 1696<->32.222, 1432<->39.773.
    _a, _b = (1696, 32.222), (1432, 39.773)
    tmainSlope = (_b[1] - _a[1]) / (_b[0] - _a[0])
    tmainOffset = _a[1] - tmainSlope * _a[0]

    headCatalog = {"G532": ("Genesis CX-Vis", 7.344)}

    class NotCalibrated(HOPSInterface.NotSupported):
        pass

    def __init__(self, url=None, serialNumber=None, bus=None):
        self.url = url or self.defaultUrl
        self.serialNumber = serialNumber
        self._bus = bus            # injectable for tests (a MockHOPSBus)
        self.i2c = None
        self._setpointWatts = 0.0
        self.powerReadCountsPerWatt = None  # set after an emission calibration

    def open(self):
        try:
            self.i2c = HOPSNativeI2C(self._bus) if self._bus is not None else HOPSNativeI2C.open(self.url)
        except HOPSInterface.Unavailable:
            raise
        except Exception as error:
            raise HOPSInterface.Unavailable(
                "Could not open the HOPS FT2232 over pyftdi/libusb: {0}".format(error)) from error

    def close(self):
        if self.i2c is not None:
            self.i2c.close()
            self.i2c = None

    def identity(self) -> dict:
        headType = self.i2c.readEepromString(self.HEAD_TYPE_REG)
        model, maxPower = self.headCatalog.get(headType, (headType, None))
        return {
            "model": model,
            "headType": headType,
            "serialNumber": self.i2c.readEepromString(self.HEAD_ID_REG),
            "maxPower": maxPower,
        }

    def getPower(self) -> float:
        raw = self.i2c.readAdc(self.POWER_REG)
        if raw == 0:
            return 0.0
        if self.powerReadCountsPerWatt is None:
            raise HOPSNativeInterface.NotCalibrated(
                "power ADC read is uncalibrated (raw={0}); set powerReadCountsPerWatt "
                "after calibrating against a meter during emission.".format(raw))
        return raw / self.powerReadCountsPerWatt

    def powerSetpoint(self) -> float:
        return self._setpointWatts   # DAC is write-only; report last commanded

    def setPower(self, power: float):
        self.i2c.writeDac(self.DAC_POWER_REG, int(round(power * self.dacCountsPerWatt)))
        self._setpointWatts = power

    def emissionOn(self) -> bool:
        return self.i2c.readGpioBit(self.ENABLE_BIT) == 1

    def setEmission(self, on: bool):
        self.i2c.writeGpioBit(self.ENABLE_BIT, 1 if on else 0)

    def shutterOpen(self) -> bool:
        return self.i2c.readGpioBit(self.SHUTTER_BIT) == 1

    def setShutter(self, isOpen: bool):
        self.i2c.writeGpioBit(self.SHUTTER_BIT, 1 if isOpen else 0)

    def remoteOn(self) -> bool:
        return self.i2c.readGpioBit(self.REMOTE_BIT) == 0   # active-low

    def setRemote(self, on: bool):
        self.i2c.writeGpioBit(self.REMOTE_BIT, 0 if on else 1)

    def mainTemperature(self) -> float:
        return self.tmainSlope * self.i2c.readAdc(self.TMAIN_REG) + self.tmainOffset

    # interlockOk() and faults() inherit HOPSInterface.NotSupported (the ?FF
    # decode was not reverse-engineered natively; to be fixed later).

    def diagnostics(self) -> dict:
        return {"mainTemperature": self.mainTemperature()}


class MockHOPSBus:
    """In-memory pyftdi-style I2C bus for tests. Seeded to the lab G532 snapshot."""

    def __init__(self):
        self.eeprom = {}
        self._seed(0x00, "G532")
        self._seed(0x10, "VH5359")
        self._seed(0x60, "DE")
        self.adc = {0xE4: 0x0000, 0x94: 1556}
        self.gpio = {0x00: 0x00, 0x02: 0x00, 0x06: 0xFF}
        self.dacCode = None

    def _seed(self, base, text):
        for offset, char in enumerate(text.encode("ascii")):
            self.eeprom[base + offset] = char
        self.eeprom[base + len(text)] = 0x00

    def get_port(self, address):
        return MockHOPSBus._Port(self, address)

    class _Port:
        def __init__(self, bus, address):
            self.bus = bus
            self.address = address

        def exchange(self, out, readlen=0):
            out = list(out)
            if self.address == HOPSNativeI2C.EEPROM:
                return bytes([self.bus.eeprom.get(out[1], 0x00)])
            if self.address == HOPSNativeI2C.ADC:
                value = self.bus.adc.get(out[0], 0)
                return bytes([(value >> 8) & 0xFF, value & 0xFF])
            if self.address == HOPSNativeI2C.GPIO:
                source = 0x02 if out[0] == 0x00 else out[0]   # input mirrors output
                return bytes([self.bus.gpio.get(source, 0x00)])
            return b""

        def write(self, out):
            out = list(out)
            if self.address == HOPSNativeI2C.GPIO:
                self.bus.gpio[out[0]] = out[1]
            elif self.address == HOPSNativeI2C.DAC:
                self.bus.dacCode = (out[1] << 8) | out[2]
