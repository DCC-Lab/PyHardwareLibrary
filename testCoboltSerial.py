import unittest
import time
from threading import Thread, Lock

from serial import *
from CommunicationPort import *
from CoboltDebugSerial import *

class BaseTestCases:

    class TestCoboltSerialPort(unittest.TestCase):
        port = None

        def testCreate(self):
            self.assertIsNotNone(self.port)

        def testLaserOn(self):
            self.port.writeString('l1\r')
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readString()

        def testLaserOff(self):
            self.port.writeString('l0\r')
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readString()

        def testReadPower(self):
            self.port.writeStringExpectMatchingString('pa?\r',replyPattern='\\d+.\\d+')

        def testReadSetPower(self):
            self.port.writeStringExpectMatchingString('p?\r',replyPattern='\\d+.\\d+')

        def testReadInterlock(self):
            self.port.writeStringExpectMatchingString('p?\r',replyPattern='\\d+.\\d+')

        def testWriteSetPower(self):
            self.port.writeString('p 0.001\r')
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readString()

        def testReadSerialNumber(self):
            self.port.writeStringExpectMatchingString('sn?\r',replyPattern='\\d+')



class TestDebugCoboltSerialPort(BaseTestCases.TestCoboltSerialPort):

    def setUp(self):
        self.port = CommunicationPort(port=CoboltDebugSerial())
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()

@unittest.skip
class TestRealCoboltSerialPort(BaseTestCases.TestCoboltSerialPort):

    def setUp(self):
        self.port = CommunicationPort(port="COM5")
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()

if __name__ == '__main__':
    unittest.main()
