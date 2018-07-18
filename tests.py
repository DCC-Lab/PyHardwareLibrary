import unittest
from SerialPort import *

class TestSerialPortWithEcho(unittest.TestCase):
    serialPort = SerialPort("/dev/cu.usbserial-DPB3LCH1")

    def setUp(self):
        self.assertIsNotNone(self.serialPort)
        self.serialPort.open()

    def tearDown(self):
        self.serialPort.close()

    def testCreate(self):
        self.assertIsNotNone(self.serialPort)

if __name__ == '__main__':
    unittest.main()
