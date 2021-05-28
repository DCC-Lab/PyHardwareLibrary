import env # modifies path
import unittest
import time
import os
from struct import *

from hardwarelibrary.communication import *
import serial

class TestSutter(unittest.TestCase):
    def setUp(self):
        self.port = None
        self.portPath = None

        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid == 4930 and port.pid == 1: # Sutter Instruments
                self.portPath = port.device

        if self.portPath is None:
            self.fail("No Sutter connected. Giving up.")

    def tearDown(self):
        if self.port is not None:
            self.port.close()

    def testPySerialPortNotNoneWhenEmpty(self):
        port = serial.Serial()
        self.assertIsNotNone(port)

    def testPySerialPortCannotOpenWhenEmpty(self):
        port = serial.Serial()
        self.assertIsNotNone(port)
        with self.assertRaises(Exception):
            port.open()

    def testPySerialPortSutter(self):
        self.port = serial.Serial(self.portPath)
        self.assertIsNotNone(self.port)
        with self.assertRaises(Exception):
            # ALready open will raise exception
            self.port.open()
        self.port.close()

    def testPortClosesProperly(self):
        self.port = serial.Serial(self.portPath, timeout=10, baudrate=128000)
        self.port.close()
        self.assertFalse(self.port.is_open)

    def testPortCanSteTimeoutLater(self):
        self.port = serial.Serial(self.portPath, timeout=10, baudrate=128000)
        self.port.timeout = 1

        self.assertEqual(self.port.timeout, 1)

    def testPySerialPortSutterReadCommand(self):
        self.port = serial.Serial(self.portPath, timeout=10, baudrate=128000)

        x,y,z  = 100000,0,0 
        commandBytes = pack('<clllc', b'M', x, y, z, b'\r')
        nBytes = self.port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))

        replyBytes = self.port.read(1)
        self.assertTrue(replyBytes == b"\r")


    def testSutterLongMoveCommandReturnZerosIfNotEnoughTime(self):
        self.port = serial.Serial(self.portPath, timeout=10, baudrate=128000)

        x,y,z  = 400000,400000,400000 
        commandBytes = pack('<clllc', b'M', x, y, z, b'\r')
        nBytes = self.port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))

        replyBytes = self.port.read(1)
        self.assertTrue(replyBytes == b"\r")

        x,y,z  = 0,0,0 
        commandBytes = pack('<clllc', b'M', x, y, z, b'\r')
        nBytes = self.port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))

        replyBytes = self.port.read(1)
        self.assertTrue(replyBytes == b"\r")

        # Buffer must be empty
        self.port.timeout = 0.1
        replyBytes = self.port.read(1)
        self.assertTrue(len(replyBytes) == 0)


    def testSutterReadPositionOnce(self):
        self.port = serial.Serial(self.portPath, timeout=10, baudrate=128000)
        
        commandBytes = pack('<cc', b'C', b'\r')
        nBytes = self.port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))

        replyBytes = self.port.read(14)
        info = unpack("<clllc", replyBytes)
        self.assertTrue(len(replyBytes) == 14)
        self.assertTrue(info[0] == b'\x01')

        # Buffer must be empty
        self.port.timeout = 0.1
        replyBytes = self.port.read(1)
        self.assertTrue(len(replyBytes) == 0)


    def testSutterReadPositionManyTimes(self):
        self.port = serial.Serial(self.portPath, timeout=10, baudrate=128000)

        for i in range(6):        
            commandBytes = pack('<cc', b'C', b'\r')
            nBytes = self.port.write(commandBytes)
            self.assertTrue(nBytes == len(commandBytes))

            replyBytes = self.port.read(14)
            self.assertTrue(len(replyBytes) == 14)
            info = unpack("<clllc", replyBytes)

            # Buffer must be empty
            self.port.timeout = 0.1
            replyBytes = self.port.read(1)
            self.assertTrue(len(replyBytes) == 0)

    def testSutterReadPositionManyTimesWith13BytesOnly(self):
        self.port = serial.Serial(self.portPath, timeout=10, baudrate=128000)

        with self.assertRaises(Exception):
            for i in range(6):        
                commandBytes = pack('<cc', b'C', b'\r')
                nBytes = self.port.write(commandBytes)
                self.assertTrue(nBytes == len(commandBytes))

                replyBytes = self.port.read(13)
                info = unpack("<clll", replyBytes)
                self.assertTrue(len(replyBytes) == 13)
                self.assertTrue(info[0] == b'\x01') # will fail on 2nd attempt



if __name__ == '__main__':
    unittest.main()
