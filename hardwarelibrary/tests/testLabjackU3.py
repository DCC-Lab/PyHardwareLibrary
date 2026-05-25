import env
import unittest
import time
import u3

from hardwarelibrary.devicemanager import *
from hardwarelibrary.notificationcenter import NotificationCenter
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState, PhysicalDeviceNotification
from hardwarelibrary.daq import LabjackDevice, DebugLabjackDevice
from enum import Enum
from typing import Union, Optional, Protocol

class TestLabjackDevice(unittest.TestCase):
    # The U3 DAC outputs are PWM-based, smoothed by a 2nd-order ~16 Hz low-pass
    # filter (~10 ms time constant), so an AIN read immediately after setting a DAC
    # returns the previous value. Wait for the output to settle before reading back.
    analogSettlingTime = 0.15

    def settledAnalogVoltage(self, value, channel):
        self.device.setAnalogVoltage(value=value, channel=channel)
        time.sleep(self.analogSettlingTime)
        return self.device.getAnalogVoltage(channel=channel)

    def setUp(self):
        super().setUp()
        self.device = LabjackDevice()
        self.assertIsNotNone(self.device)
        try:
            self.device.initializeDevice()
        except PhysicalDevice.UnableToInitialize as err:
            cause = err.args[0] if err.args else None
            if isinstance(cause, u3.LabJackException):
                self.skipTest("No Labjack connected")
            raise

    def skipUnlessAnalogLoopback(self, channel):
        low = self.settledAnalogVoltage(0.5, channel)
        high = self.settledAnalogVoltage(2.5, channel)
        if high - low < 1.0:
            self.skipTest(f"DAC{channel} not jumpered to AIN{channel}")

    def skipUnlessDigitalLoopback(self, outputChannel, inputChannel):
        self.device.setDigitalValue(channel=outputChannel, value=True)
        high = self.device.getDigitalValue(channel=inputChannel)
        self.device.setDigitalValue(channel=outputChannel, value=False)
        low = self.device.getDigitalValue(channel=inputChannel)
        if not (high and not low):
            self.skipTest(f"FIO{outputChannel} not jumpered to FIO{inputChannel}")

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
        self.skipUnlessAnalogLoopback(0)
        expectedValue = 1.5
        actualValue = self.settledAnalogVoltage(expectedValue, 0)
        self.assertIsNotNone(actualValue)
        self.assertAlmostEqual(actualValue, expectedValue, 1)

    def testSetAnalogValueChannel1(self):
        self.skipUnlessAnalogLoopback(1)
        expectedValue = 1.1
        actualValue = self.settledAnalogVoltage(expectedValue, 1)
        self.assertIsNotNone(actualValue)
        self.assertAlmostEqual(actualValue, expectedValue, 1)

    def testMeasureAnalogSettlingTime(self):
        channel = 0
        self.skipUnlessAnalogLoopback(channel)

        target = 3.0
        tolerance = 0.05
        timeout = 1.0

        self.device.setAnalogVoltage(value=0.0, channel=channel)
        time.sleep(0.5)

        start = time.perf_counter()
        self.device.setAnalogVoltage(value=target, channel=channel)
        settlingTime = None
        reads = 0
        while time.perf_counter() - start < timeout:
            reads += 1
            if abs(self.device.getAnalogVoltage(channel=channel) - target) <= tolerance:
                settlingTime = time.perf_counter() - start
                break

        self.assertIsNotNone(settlingTime, f"AIN{channel} never reached {target} V within {timeout} s")
        print(f"\nDAC{channel}->AIN{channel} full-scale step settled within {tolerance} V "
              f"in {settlingTime * 1000:.1f} ms over {reads} reads (USB + DAC RC + ADC)")
        self.assertLess(settlingTime, self.analogSettlingTime,
                        f"measured settling {settlingTime * 1000:.1f} ms exceeds "
                        f"analogSettlingTime {self.analogSettlingTime * 1000:.0f} ms used by the suite")

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
        outputChannel = 6
        inputChannel = 7
        self.skipUnlessDigitalLoopback(outputChannel, inputChannel)

        expectedValue = True
        loops = 1000
        maxAttempts = 10
        while loops > 0:
            loops -= 1
            self.device.setDigitalValue(channel=outputChannel, value=expectedValue)

            actualValue = None
            attempts = 0
            while actualValue != expectedValue and attempts < maxAttempts:
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

    def testOpenBySerialNumber(self):
        serialNumber = str(self.device.configuration()['SerialNumber'])
        self.device.shutdownDevice()
        try:
            bySerial = LabjackDevice(serialNumber=serialNumber)
            bySerial.initializeDevice()
            self.assertEqual(str(bySerial.configuration()['SerialNumber']), serialNumber)
            bySerial.shutdownDevice()
        finally:
            self.device.initializeDevice()

    def testIsHighVoltage(self):
        self.assertIsInstance(self.device.isHighVoltage, bool)

    def testGetTemperature(self):
        kelvin = self.device.getTemperature()
        self.assertGreater(kelvin, 250)
        self.assertLess(kelvin, 350)

    def testToggleLED(self):
        self.device.toggleLED()

    def testSetAnalogVoltageInvalidChannel(self):
        with self.assertRaises(ValueError):
            self.device.setAnalogVoltage(value=1.0, channel=2)

    def testConfigureAnalogIO(self):
        self.device.configureAnalogIO({})

    def testConfigureDigitalIO(self):
        self.device.configureDigitalIO({})

class TestDebugLabjackDevice(unittest.TestCase):
    def setUp(self):
        self.device = DebugLabjackDevice()
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()

    def testCreate(self):
        self.assertIsNotNone(self.device)
        self.assertIsNone(self.device.dev)

    def testInitializeAndShutdown(self):
        device = DebugLabjackDevice()
        device.initializeDevice()
        device.shutdownDevice()

    def testIsHighVoltage(self):
        self.assertFalse(self.device.isHighVoltage)

    def testConfiguration(self):
        config = self.device.configuration()
        self.assertEqual(config['DeviceName'], 'DebugU3')

    def testSetConfiguration(self):
        with self.assertRaises(NotImplementedError):
            self.device.setConfiguration({})

    def testGetAnalogVoltageDefault(self):
        value = self.device.getAnalogVoltage(channel=0)
        self.assertEqual(value, 0.0)

    def testSetAndGetAnalogVoltage(self):
        self.device.setAnalogVoltage(value=2.5, channel=0)
        self.assertAlmostEqual(self.device.getAnalogVoltage(channel=0), 2.5)

    def testSetAnalogVoltageChannel1(self):
        self.device.setAnalogVoltage(value=1.1, channel=1)
        self.assertAlmostEqual(self.device.getAnalogVoltage(channel=1), 1.1)

    def testSetAnalogVoltageInvalidChannel(self):
        with self.assertRaises(ValueError):
            self.device.setAnalogVoltage(value=1.0, channel=2)

    def testSetAndGetDigitalValue(self):
        self.device.setDigitalValue(value=True, channel=4)
        self.assertTrue(self.device.getDigitalValue(channel=4))

    def testGetDigitalValueDefault(self):
        self.assertFalse(self.device.getDigitalValue(channel=4))

    def testToggleDigitalValue(self):
        channel = 6
        self.device.setDigitalValue(value=True, channel=channel)
        self.assertTrue(self.device.getDigitalValue(channel=channel))
        self.device.setDigitalValue(value=False, channel=channel)
        self.assertFalse(self.device.getDigitalValue(channel=channel))

    def testGetTemperature(self):
        self.assertAlmostEqual(self.device.getTemperature(), 298.0)

    def testToggleLED(self):
        self.device.toggleLED()

    def testConfigureAnalogIO(self):
        self.device.configureAnalogIO({'FIOAnalog': 0xFF})

    def testConfigureDigitalIO(self):
        self.device.configureDigitalIO({'FIOAnalog': 0x00})


if __name__ == '__main__':
    unittest.main()
