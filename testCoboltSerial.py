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

        def testCantReopen(self):
            self.assertTrue(self.port.isOpen)
            with self.assertRaises(Exception) as context:
                self.port.open()

        def testCloseReopen(self):
            self.assertTrue(self.port.isOpen)
            self.port.close()
            self.port.open()

        def testCloseTwice(self):
            self.assertTrue(self.port.isOpen)
            self.port.close()
            self.port.close()

        def testLaserOn(self):
            autostartString = self.port.writeStringReadFirstMatchingGroup('@cobas?\r',replyPattern='(1|0)')

            if not bool(autostartString):
                self.port.writeStringExpectMatchingString('l1\r',replyPattern='OK')

        def testLaserOff(self):
            self.port.writeStringExpectMatchingString('l0\r',replyPattern='OK')

        def testReadPower(self):
            self.port.writeStringExpectMatchingString('pa?\r',replyPattern='\\d+.\\d+')

        def testReadSetPower(self):
            self.port.writeStringExpectMatchingString('p?\r',replyPattern='\\d+.\\d+')

        def testReadInterlock(self):
            self.port.writeStringExpectMatchingString('p?\r',replyPattern='\\d+.\\d+')

        def testWriteSetPower(self):
            self.port.writeStringExpectMatchingString('p 0.001\r','OK')

        def testReadSerialNumber(self):
            self.port.writeStringExpectMatchingString('sn?\r',replyPattern='\\d+')

        def testUnknownCommand(self):
            self.port.writeStringExpectMatchingString('nothing useful\r',replyPattern="Syntax error")


class TestDebugCoboltSerialPort(BaseTestCases.TestCoboltSerialPort):

    def setUp(self):
        self.port = CommunicationPort(port=CoboltDebugSerial())
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()

class TestRealCoboltSerialPort(BaseTestCases.TestCoboltSerialPort):

    def setUp(self):
        try:
            self.port = CommunicationPort(port="COM5")
            self.port.open()
        except:
            raise unittest.SkipTest("No cobolt serial port at COM5")

    def tearDown(self):
        self.port.close()

if __name__ == '__main__':
    unittest.main()
