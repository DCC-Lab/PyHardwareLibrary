import env # modifies path
import unittest
import time
import os
from struct import *

from hardwarelibrary.communication import *
import serial

class TestPySerial(unittest.TestCase):
    def setUp(self):
        if os.name == 'nt':
            self.portPath = "COM4"
        else:
            self.portPath = "/dev/cu.usbserial-SI8YCLBE"

    def testPySerialPortNotNoneWhenEmpty(self):
        port = serial.Serial()
        self.assertIsNotNone(port)

    def testPySerialPortCannotOpenWhenEmpty(self):
        port = serial.Serial()
        self.assertIsNotNone(port)
        with self.assertRaises(Exception):
            port.open()

    def testPySerialPortSutter(self):
        port = serial.Serial(self.portPath)
        self.assertIsNotNone(port)
        with self.assertRaises(Exception):
            # ALready open will raise exception
            port.open()
        port.close()

    def testPySerialPortSutterReadCommand(self):
        x,y,z  = 100000,0,0 
        port = serial.Serial(self.portPath, timeout=5, baudrate=128000)
        commandBytes = pack('<clllc', b'M', x, y, z, b'\r')
        nBytes = port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))
        replyBytes = port.read(1)
        print(replyBytes)
        self.assertTrue(replyBytes == b"\r")
        port.close()

    def testSutterReadPosition(self):
        port = serial.Serial(self.portPath, timeout=5, baudrate=128000)
        commandBytes = pack('<cc', b'C', b'\r')
        nBytes = port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))
        replyBytes = port.read(13)
        print(replyBytes)
        info = unpack("<clll", replyBytes)
        print(info)
        print(info[1:])
        print(info[3]/16)
        self.assertTrue(len(replyBytes) == 13)
        port.close()
        self.assertFalse(port.is_open)


if __name__ == '__main__':
    unittest.main()
