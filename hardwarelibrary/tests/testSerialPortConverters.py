import env
import unittest
from unittest.mock import patch

from hardwarelibrary.communication.serialport import SerialPort


class FakePort:
    """Minimal stand-in for pyserial's ListPortInfo."""

    def __init__(self, device, vid, pid=0x0001, serial_number="SN"):
        self.device = device
        self.vid = vid
        self.pid = pid
        self.serial_number = serial_number


class TestIsGenericSerialConverter(unittest.TestCase):
    def testKnownVendorsAreConverters(self):
        for idVendor in (0x0403, 0x067b, 0x10c4, 0x1a86):
            self.assertTrue(SerialPort.isGenericSerialConverter(idVendor))

    def testUnknownVendorIsNotConverter(self):
        self.assertFalse(SerialPort.isGenericSerialConverter(0x0483))  # STM32 CDC

    def testNoneVendorIsNotConverter(self):
        self.assertFalse(SerialPort.isGenericSerialConverter(None))


class TestGenericSerialConverterPorts(unittest.TestCase):
    def testFiltersToConvertersOnly(self):
        fakePorts = [
            FakePort("/dev/cu.usbserial-FTDI", 0x0403, 0x6001, "FTFDLOTS"),
            FakePort("/dev/cu.usbserial-CP210", 0x10c4, 0xea60, "CP01"),
            FakePort("/dev/cu.usbmodem-STM32", 0x0483, 0x5740, "STM"),
            FakePort("/dev/cu.Bluetooth", None, None, None),
        ]
        with patch("hardwarelibrary.communication.serialport.comports", return_value=fakePorts):
            found = SerialPort.genericSerialConverterPorts()

        devices = [port.device for port in found]
        self.assertEqual(devices, ["/dev/cu.usbserial-FTDI", "/dev/cu.usbserial-CP210"])

    def testReturnsEmptyWhenNoConverters(self):
        fakePorts = [FakePort("/dev/cu.usbmodem-STM32", 0x0483)]
        with patch("hardwarelibrary.communication.serialport.comports", return_value=fakePorts):
            self.assertEqual(SerialPort.genericSerialConverterPorts(), [])


if __name__ == "__main__":
    unittest.main()
