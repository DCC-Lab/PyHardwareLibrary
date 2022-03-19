import env
import unittest

from hardwarelibrary.devicemanager import *
from hardwarelibrary.notificationcenter import NotificationCenter
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState, PhysicalDeviceNotification
from hardwarelibrary.daq import LabjackDevice
from enum import Enum
from typing import Union, Optional, Protocol

class TestLabjackDevice(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.device = LabjackDevice()
        self.assertIsNotNone(self.device)
        self.device.initializeDevice()

    def tearDown(self):
        super().tearDown()
        self.assertIsNotNone(self.device)
        self.device.shutdownDevice()

    def testCreate(self):
        self.assertIsNotNone(self.device)

    def testInitializeAndShutdown(self):
        self.assertIsNotNone(self.device)
        self.device.initializeDevice()
        self.device.shutdownDevice()

    @unittest.skip("Not connected like that")
    def testGetAnalogValueChannel0(self):
        # Connect AIN0 to VS
        value = self.device.getAnalogVoltage(channel=0)
        self.assertIsNotNone(value)
        self.assertAlmostEqual(value, 0, 1)

    @unittest.skip("Not connected like that")
    def testGetAnalogValueChannel1(self):
        # Connect AIN1 to GND
        value = self.device.getAnalogVoltage(channel=1)
        self.assertIsNotNone(value)
        self.assertAlmostEqual(value, 4.53, 1)

    def testSetAnalogValueChannel0(self):
        # DAC0 conected to AIN0
        expectedValue = 1.5
        self.device.setAnalogVoltage(value=expectedValue, channel=0)

        actualValue = self.device.getAnalogVoltage(channel=0)
        self.assertIsNotNone(actualValue)
        self.assertAlmostEqual(actualValue, expectedValue, 1)

    def testSetAnalogValueChannel1(self):
        # DAC1 conected to AIN1
        expectedValue = 1.1
        self.device.setAnalogVoltage(value=expectedValue, channel=1)

        actualValue = self.device.getAnalogVoltage(channel=1)
        self.assertIsNotNone(actualValue)
        self.assertAlmostEqual(actualValue, expectedValue, 1)

    def testSetDigitalValueChannel4(self):
        expectedValue = True
        channel = 4
        self.device.setDigitalValue(value=expectedValue, channel=channel)

    def testGetDigitalValueChannel4(self):
        channel = 4
        actualValue = self.device.getDigitalValue(channel=channel)
        self.assertIsNotNone(actualValue)

    def testSetDigitalValueChannel4(self):
        expectedValue = True
        channel = 4
        self.device.setDigitalValue(channel=channel, value=expectedValue)
        actualValue = self.device.getDigitalValue(channel=channel)
        self.assertIsNotNone(actualValue)
        self.assertEqual(actualValue, expectedValue)

    def testToggleDigitalValuesQuickly(self):
        expectedValue = True
        outputChannel = 6
        inputChannel = 7
        loops = 1000
        while loops > 0:
            loops -= 1
            self.device.setDigitalValue(channel=outputChannel, value=expectedValue)

            actualValue = None
            attempts = 0
            while actualValue != expectedValue:
                actualValue = self.device.getDigitalValue(channel=inputChannel)
                attempts = attempts + 1
            self.assertEqual(attempts, 1)
            self.assertEqual(actualValue, expectedValue)

            expectedValue = not expectedValue

    def testConfiguration(self):
        self.assertIsNotNone(self.device.configuration())

    def testSetConfiguration(self):
        with self.assertRaises(NotImplementedError):
            self.device.setConfiguration(None)

if __name__ == '__main__':
    unittest.main()
