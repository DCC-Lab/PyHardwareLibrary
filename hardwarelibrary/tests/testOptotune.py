import unittest
import env
import struct
from hardwarelibrary.communication import SerialPort

class TestOptotune(unittest.TestCase):
    idVendor = 0x03eb
    idProduct = 0x2018
    port = None

    def test01SerialPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.assertIsNotNone(self.port)
        self.port = None

    def test02OpenPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.port.open(baudRate=115200)
        self.assertTrue(self.port.isOpen)
        self.port.close()
        self.assertFalse(self.port.isOpen)
        self.port = None

    def test03WriteStartCommandToPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.port.open(baudRate=115200)
        self.assertTrue(self.port.isOpen)

        command = 'Start'
        self.port.writeString(command)
        reply = self.port.readString()
        self.assertTrue(reply == 'Ready\r\n')

        self.port.close()
        self.port = None

    def calculateCRC16bit(self, data) -> bytearray:
    	crc = 1234
    	crcBytes = struct.pack('<H', crc)
    	return bytearray(crcBytes)

    def test04WriteSetCurrent(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.port.open(baudRate=115200)
        self.assertTrue(self.port.isOpen)

        dataSetCurrent = bytearray(b'Aw\x02\xbb')
        crc16 = self.calculateCRC16bit(dataSetCurrent)
        dataSetCurrent.extend(crc16)
        self.port.writeData(dataSetCurrent)
        error = self.port.readString()
        self.assertTrue(error[0] == 'E')
        self.assertTrue(error[1] == '1')
        self.assertTrue(len(error) >= 5)
        self.port.close()
        self.port = None


if __name__ == '__main__':
    unittest.main()
