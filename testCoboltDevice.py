import unittest
import time
from threading import Thread, Lock

from serial import *
from CommunicationPort import *
from DebugEchoCommunicationPort import *
from CoboltDevice import *

class BaseTestCases:
    device:CoboltDevice = None

    class TestCobolt(unittest.TestCase):
    
        def testCreate(self):
            self.assertIsNotNone(self.device)

        def testDeviceCreationWithMissingPath(self):
            aDevice = CoboltDevice(bsdPath="blabla") 
            with self.assertRaises(PhysicalDeviceUnableToInitialize) as context:
                aDevice.initializeDevice()

        def testInitializeShutdown(self):
            self.device.initializeDevice()
            self.device.shutdownDevice()

        def testTurnOn(self):
            self.device.turnOn()            

        def testTurnOff(self):
            self.device.turnOff()            

        def testTurnOnOff(self):
            self.device.turnOn()            
            self.device.setPower(0.01)            
            self.assertTrue(self.device.power() == 0.01)

        def testInterloc(self):
            self.assertTrue(self.device.interlock()) 

class TestDebugCobolt(BaseTestCases.TestCobolt):

    def setUp(self):
        self.device = CoboltDevice(bsdPath="debug") 
        self.assertIsNotNone(self.device)
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()
        return

class TestRealCobolt(BaseTestCases.TestCobolt):

    def setUp(self):
        try:
            self.device = CoboltDevice(bsdPath="COM5") 
            self.device.initializeDevice()
        except:
            raise unittest.SkipTest("No CoboltDevice at COM5")

    def tearDown(self):
        self.device.shutdownDevice()
        return



if __name__ == '__main__':
    unittest.main()
