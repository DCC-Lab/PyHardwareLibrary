import unittest
import env
from hardwarelibrary.communication import SerialPort

class TestOptotune(unittest.TestCase):
    idVendor = 0x03eb
    idProduct = 0x2018
    port = None

    def testSerialPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem143101')
        self.assertIsNotNone(self.port)
        self.port = None

    def testOpenPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem143101')
        self.port.open(baudRate=38000)
        self.assertTrue(self.port.isOpen)
        self.port.close()
        self.port = None

    def testWriteSimpleCommandToPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem143101')
        self.port.open()
        self.assertTrue(self.port.isOpen)

        data = bytearray(b'')
        self.port.writeData(data)
        reply = self.port.readData(length=1)

        self.port.close()
        self.port = None



if __name__ == '__main__':
    unittest.main()
