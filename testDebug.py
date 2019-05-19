import unittest
from serial import *
from SerialPort import *

payloadData = b'1234'
payloadString = '1234\n'

class BaseTestCases:

    class TestEchoPort(unittest.TestCase):
        port = None

        def testCreate(self):
            self.assertIsNotNone(self.port)

        def testWriteData(self):
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))

        def testWriteDataReadEcho(self):
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))

            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData)

        def testWriteDataReadEchoSequence(self):
            nBytes = self.port.writeData(payloadData)
            nBytes = self.port.writeData(payloadData)

            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData)
            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData)

        def testWriteDataReadEchoLarge(self):
            for i in range(100):
                nBytes = self.port.writeData(payloadData)

            for i in range(100):
                data = self.port.readData(length=len(payloadData))
                self.assertTrue(data == payloadData)

        def testWriteString(self):
            nBytes = self.port.writeString(payloadString)
            self.assertTrue(nBytes == len(payloadString))

        def testWriteStringReadEcho(self):
            nBytes = self.port.writeString(payloadString)
            self.assertTrue(nBytes == len(payloadString))

            string = self.port.readString()
            self.assertTrue(string == payloadString, "String {0}, payload:{1}".format(string, payloadString))

        def testWriteStringReadEchoSequence(self):
            nBytes = self.port.writeString(payloadString)
            nBytes = self.port.writeString(payloadString)

            string = self.port.readString()
            self.assertTrue(string == payloadString)
            string = self.port.readString()
            self.assertTrue(string == payloadString)

        def testWriteStringReadEchoLarge(self):
            for i in range(100):
                nBytes = self.port.writeString(payloadString)

            for i in range(100):
                string = self.port.readString()
                self.assertTrue(string == payloadString)

        def testTimeoutReadData(self):
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readData(1)

            self.port.writeData(payloadData)
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readData(len(payloadData)+1)

class TestDebugEchoPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        self.port = DebugEchoSerialPort()
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()


class TestRealEchoPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        try:
            self.port = SerialPort("/dev/cu.usbserial-ftDXIKC4")
            self.assertIsNotNone(self.port)
            self.port.open()
        except:
            self.fail("Unable to setUp serial port")


    def tearDown(self):
        self.port.close()


if __name__ == '__main__':
    unittest.main()
