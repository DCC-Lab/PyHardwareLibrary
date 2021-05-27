import env # modifies path
import unittest
import time
import os
from struct import *

from hardwarelibrary.communication import *
import serial

class TestPySerial(unittest.TestCase):
    def setUp(self):
        self.port = None
        if os.name == 'nt':
            self.portPath = "COM4"
        else: # macOS
            self.portPath = "/dev/cu.usbserial-SI8YCLBE"

    def tearDown(self):
        self.port.close()

    def testPySerialPortNotNoneWhenEmpty(self):
        self.port = serial.Serial()
        self.assertIsNotNone(self.port)

    def testPySerialPortCannotOpenWhenEmpty(self):
        self.port = serial.Serial()
        self.assertIsNotNone(self.port)
        with self.assertRaises(Exception):
            self.port.open()

    def testPySerialPortSutter(self):
        self.port = serial.Serial(self.portPath)
        self.assertIsNotNone(self.port)
        with self.assertRaises(Exception):
            # ALready open will raise exception
            self.port.open()
        self.port.close()

    def testPortClosesProperly(self):
        self.port = serial.Serial(self.portPath, timeout=5, baudrate=128000)
        self.port.close()
        self.assertFalse(self.port.is_open)
        
    def testPySerialPortSutterReadCommand(self):
        x,y,z  = 100000,0,0 
        self.port = serial.Serial(self.portPath, timeout=5, baudrate=128000)
        commandBytes = pack('<clllc', b'M', x, y, z, b'\r')
        nBytes = self.port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))
        replyBytes = self.port.read(1)
        print(replyBytes)
        self.assertTrue(replyBytes == b"\r")
        self.port.close()

    def testSutterReadPosition(self):
        self.port = serial.Serial(self.portPath, timeout=5, baudrate=128000)
        
        commandBytes = pack('<cc', b'C', b'\r')
        nBytes = self.port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))

        replyBytes = self.port.read(13)
        print(replyBytes)
        info = unpack("<clll", replyBytes)
        print(info)
        print(info[1:])
        print(info[3]/16)
        self.assertTrue(len(replyBytes) == 13)


if __name__ == '__main__':
    unittest.main()
