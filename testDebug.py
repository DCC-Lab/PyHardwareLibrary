import unittest
from serial import *
from SerialPort import *

payload = b'1234'

class TestEchoPort(unittest.TestCase):
    port = None

    def setUp(self):
        self.port = DebugEchoSerialPort()
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()

    def testCreate(self):
        self.assertIsNotNone(self.port)

    def testWrite(self):
        nBytes = self.port.writeData(payload)
        self.assertTrue(nBytes == len(payload))

    def testWriteReadEcho(self):
        nBytes = self.port.writeData(payload)
        self.assertTrue(nBytes == len(payload))

        data = self.port.readData(length=len(payload))
        self.assertTrue(data == payload)

    def testWriteReadEchoSequence(self):
        nBytes = self.port.writeData(payload)
        nBytes = self.port.writeData(payload)

        data = self.port.readData(length=len(payload))
        self.assertTrue(data == payload)
        data = self.port.readData(length=len(payload))
        self.assertTrue(data == payload)

    def testWriteReadEchoLarge(self):
        for i in range(100):
            nBytes = self.port.writeData(payload)

        for i in range(100):
            data = self.port.readData(length=len(payload))
            self.assertTrue(data == payload)

if __name__ == '__main__':
    unittest.main()
