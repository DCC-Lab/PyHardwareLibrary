import unittest
import time
from threading import Thread, Lock

from serial import *
from CommunicationPort import *
from DebugEchoCommunicationPort import *

class BaseTestCases:
    device:CoboltDevice = None

    class TestCobolt(unittest.TestCase):
    
        def create(self):




class TestDebugCobolt(BaseTestCases.TestCobolt):

    def setUp(self):
        self.port = ()
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()


class TestRealCobolt(BaseTestCases.TestCobolt):

    def setUp(self):
        self.device = 

    def tearDown(self):
        self.port.close()


class TestRealEchoPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        try:
            self.port = CommunicationPort("/dev/cu.usbserial-ftDXIKC4")
            self.assertIsNotNone(self.port)
            self.port.open()
        except:
            self.fail("Unable to setUp serial port")


    def tearDown(self):
        self.port.close()


if __name__ == '__main__':
    unittest.main()
