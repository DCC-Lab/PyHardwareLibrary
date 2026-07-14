import env
import unittest

from hardwarelibrary.powermeters import FieldMasterDevice, DebugFieldMasterDevice
from hardwarelibrary.powermeters import (
    WavelengthCalibrationCapability, AutoScaleCapability, ScaleCapability,
)
from hardwarelibrary.powermeters.powermeterdevice import PowerMeterNotification
from hardwarelibrary.notificationcenter import NotificationCenter


class TestDebugFieldMasterDevice(unittest.TestCase):
    def setUp(self):
        self.device = DebugFieldMasterDevice()
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()
        NotificationCenter().clear()

    def testCreate(self):
        self.assertIsNotNone(self.device)

    def testMeasureAbsolutePower(self):
        power = self.device.measureAbsolutePower()
        self.assertIsInstance(power, float)
        self.assertGreater(power, 0.0)

    def testMeasureAbsolutePowerPostsNotification(self):
        self.received = None

        def handler(notification):
            self.received = notification.userInfo

        NotificationCenter().addObserver(self, handler, PowerMeterNotification.didMeasure)
        power = self.device.measureAbsolutePower()
        self.assertEqual(self.received, power)

    def testGetCalibrationWavelength(self):
        self.assertEqual(self.device.getCalibrationWavelength(), 1064.0)

    def testSetCalibrationWavelength(self):
        self.device.setCalibrationWavelength(532.0)
        self.assertEqual(self.device.getCalibrationWavelength(), 532.0)

    def testEnergy(self):
        self.assertIsInstance(self.device.getEnergy(), float)


class TestFieldMasterCapabilities(unittest.TestCase):
    def setUp(self):
        self.device = DebugFieldMasterDevice()

    def testDeclaresWavelengthCalibrationCapability(self):
        self.assertTrue(self.device.hasCapability(WavelengthCalibrationCapability))

    def testDoesNotDeclareScaleCapabilities(self):
        self.assertFalse(self.device.hasCapability(AutoScaleCapability))
        self.assertFalse(self.device.hasCapability(ScaleCapability))

    def testCapabilitiesListsOnlyDeclaredMixins(self):
        self.assertEqual(self.device.capabilities(), [WavelengthCalibrationCapability])

    def testCapabilitiesExcludeDeviceClass(self):
        # The driver is itself a Capability subclass, but capabilities() must
        # report only the mixins, never the device class or its base.
        capabilities = self.device.capabilities()
        self.assertNotIn(DebugFieldMasterDevice, capabilities)
        self.assertNotIn(FieldMasterDevice, capabilities)


class TestFieldMasterDevice(unittest.TestCase):
    def setUp(self):
        self.device = FieldMasterDevice()
        try:
            self.device.initializeDevice()
        except Exception:
            self.skipTest("No FieldMaster (on its Home screen) connected")

    def tearDown(self):
        self.device.shutdownDevice()

    def testMeasureAbsolutePower(self):
        power = self.device.measureAbsolutePower()
        self.assertIsInstance(power, float)
        print("FieldMaster power:", power)

    def testGetCalibrationWavelength(self):
        wavelength = self.device.getCalibrationWavelength()
        self.assertGreater(wavelength, 100)
        print("FieldMaster calibration wavelength (nm):", wavelength)


if __name__ == "__main__":
    unittest.main()
