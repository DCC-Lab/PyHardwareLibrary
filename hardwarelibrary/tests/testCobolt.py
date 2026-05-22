import env
import unittest
import time

from hardwarelibrary.physicaldevice import DeviceState
from hardwarelibrary.sources.cobolt import CoboltDevice, CoboltCantTurnOnWithAutostartOn


class TestDebugCoboltDevice(unittest.TestCase):
    def setUp(self):
        self.device = CoboltDevice(portPath="debug")
        self.device.initializeDevice()

    def tearDown(self):
        if self.device.state == DeviceState.Ready:
            self.device.shutdownDevice()

    def testInitializedToReady(self):
        self.assertEqual(self.device.state, DeviceState.Ready)

    def testGetPower(self):
        self.assertIsNotNone(self.device.power())

    def testInterlockClosed(self):
        self.assertTrue(self.device.interlock())

    def testBootsWithAutostartOn(self):
        self.assertTrue(self.device.autostartIsOn())

    def testTurnOnRefusedWhileAutostartOn(self):
        with self.assertRaises(CoboltCantTurnOnWithAutostartOn):
            self.device.turnOn()

    def testTurnOnAndOffWithAutostartOff(self):
        self.device.turnAutostartOff()
        self.device.turnOn()
        self.assertTrue(self.device.isLaserOn())
        self.device.turnOff()
        self.assertFalse(self.device.isLaserOn())

    def testSetPower(self):
        self.device.setPower(0.5)
        time.sleep(1.0)  # the debug port ramps power in a background thread
        self.assertAlmostEqual(self.device.power(), 0.5, places=1)

    def testShutdownReleasesPort(self):
        self.device.shutdownDevice()
        self.assertEqual(self.device.state, DeviceState.Recognized)
        self.assertIsNone(self.device.port)


class TestCoboltDevice(unittest.TestCase):
    def setUp(self):
        try:
            self.device = CoboltDevice()
            self.device.initializeDevice()
        except Exception:
            self.skipTest("No Cobolt laser connected")

    def tearDown(self):
        if self.device.state == DeviceState.Ready:
            self.device.shutdownDevice()

    def testReadPower(self):
        self.assertIsNotNone(self.device.power())


if __name__ == "__main__":
    unittest.main()
