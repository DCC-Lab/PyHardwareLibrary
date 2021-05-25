import env # modifies path
import unittest
import time
from threading import Thread, Lock
import random
import array
import os
from struct import *

from hardwarelibrary.communication import *
import serial

"""
class TestSerialPortFromDaniel(unittest.TestCase):
    def testInit(self):
        self.assertTrue(True)

    def testPortFound(self):
        port = SerialPort(idVendor=4930, idProduct=1)
        self.assertIsNotNone(port)

    def testPortOpen(self):
        port = SerialPort(idVendor=4930, idProduct=1)
        self.assertIsNotNone(port)
        port.open()
"""


class TestPySerial(unittest.TestCase):

    def testPySerialPortNotNoneWhenEmpty(self):
        port = serial.Serial()
        self.assertIsNotNone(port)

    def testPySerialPortCannotOpenWhenEmpty(self):
        port = serial.Serial()
        self.assertIsNotNone(port)
        with self.assertRaises(Exception):
            port.open()

    def testPySerialPortSutter(self):
        port = serial.Serial("/dev/cu.usbserial-SI8YCLBE")
        self.assertIsNotNone(port)
        with self.assertRaises(Exception):
            # ALready open will raise exception
            port.open()
        port.close()


    def testPySerialPortSutterReadCommand(self):
        x,y,z  = 100000,0,0 
        port = serial.Serial("/dev/cu.usbserial-SI8YCLBE", timeout=5, baudrate=128000)
        commandBytes = pack('<clllc', b'M', x, y, z, b'\r')
        nBytes = port.write(commandBytes)
        self.assertTrue(nBytes == len(commandBytes))
        replyBytes = port.read(1)
        print(replyBytes)
        self.assertTrue(replyBytes == b"\r")
        port.close()

    def testSutterReadPosition(self):
        port = serial.Serial("/dev/cu.usbserial-SI8YCLBE", timeout=5, baudrate=128000)
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
