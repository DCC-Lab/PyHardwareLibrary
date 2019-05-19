import unittest
from SerialPort import *

payload = b'1234'

class TestSerialPortWithEcho(unittest.TestCase):
    serialPort = DebugEchoSerialPort()

    def setUp(self):
        self.assertIsNotNone(self.serialPort)
        self.serialPort.open()

    def tearDown(self):
        self.serialPort.close()

    def testCreate(self):
        self.assertIsNotNone(self.serialPort)

    def testWrite(self):
        nBytes = self.serialPort.writeData(payload)
        self.assertTrue(nBytes == len(payload))

    def testWriteReadEcho(self):
        nBytes = self.serialPort.writeData(payload)
        self.assertTrue(nBytes == len(payload))

        data = self.serialPort.readData(length=len(payload))
        self.assertTrue(data == payload)



if __name__ == '__main__':
    unittest.main()
