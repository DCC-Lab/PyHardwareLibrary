import env
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.powerstrips import (
    PwrUSBDevice, DebugPwrUSBDevice,
    OutletSwitchingCapability, DefaultOutletCapability, CurrentMeteringCapability,
)


class TestDebugPwrUSBDevice(unittest.TestCase):
    def setUp(self):
        self.device = DebugPwrUSBDevice()
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()

    def testCreate(self):
        self.assertIsNotNone(self.device)

    def testInitializeAndShutdown(self):
        device = DebugPwrUSBDevice()
        device.initializeDevice()
        device.shutdownDevice()

    def testOutletCount(self):
        self.assertEqual(self.device.outletCount, 3)

    def testCapabilities(self):
        capabilities = self.device.capabilities()
        self.assertIn(OutletSwitchingCapability, capabilities)
        self.assertIn(DefaultOutletCapability, capabilities)
        self.assertIn(CurrentMeteringCapability, capabilities)

    def testHasCapability(self):
        self.assertTrue(self.device.hasCapability(OutletSwitchingCapability))
        self.assertTrue(self.device.hasCapability(CurrentMeteringCapability))

    def testAllOutletsStartOff(self):
        for outlet in (1, 2, 3):
            self.assertFalse(self.device.isOutletOn(outlet))

    def testTurnOutletOnAndOff(self):
        for outlet in (1, 2, 3):
            self.device.turnOutletOn(outlet)
            self.assertTrue(self.device.isOutletOn(outlet))
            self.device.turnOutletOff(outlet)
            self.assertFalse(self.device.isOutletOn(outlet))

    def testSetOutletState(self):
        self.device.setOutletState(2, True)
        self.assertTrue(self.device.isOutletOn(2))
        self.assertFalse(self.device.isOutletOn(1))
        self.assertFalse(self.device.isOutletOn(3))

    def testSwitchingSendsCorrectBytesPerOutlet(self):
        # The mock port decodes the real command bytes; confirm each outlet's
        # ON/OFF maps to exactly that outlet on the wire.
        self.device.turnOutletOn(3)
        self.assertEqual(self.device.port.outletStates, [False, False, True])

    def testDefaultStateSetters(self):
        self.device.setOutletDefaultOn(1)
        self.device.setOutletDefaultOff(2)
        self.assertEqual(self.device.port.defaultStates, [True, False, False])

    def testInvalidOutletRaises(self):
        for outlet in (0, 4, -1):
            with self.assertRaises(ValueError):
                self.device.turnOutletOn(outlet)
            with self.assertRaises(ValueError):
                self.device.isOutletOn(outlet)

    def testDeviceType(self):
        self.assertEqual(self.device.deviceType(), "Smart")

    def testGetCurrent(self):
        current = self.device.current()
        self.assertAlmostEqual(current, 0.250)

    def testAccumulatedChargeAndReset(self):
        self.device.port.chargeMilliampMinutes = 120000
        self.assertAlmostEqual(self.device.accumulatedCharge(), 2.0)
        self.device.resetAccumulatedCharge()
        self.assertAlmostEqual(self.device.accumulatedCharge(), 0.0)


class TestPwrUSBDevice(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.device = PwrUSBDevice()
        try:
            self.device.initializeDevice()
        except PhysicalDevice.UnableToInitialize as error:
            cause = error.args[0] if error.args else None
            # No strip attached raises an OSError from hidapi; a host without the
            # optional hidapi dependency (e.g. CI, which installs only [dev])
            # raises ImportError. Either way there is no hardware to exercise, so
            # skip rather than fail.
            if isinstance(cause, (OSError, ImportError)):
                self.skipTest("No PwrUSB connected (or hidapi not installed)")
            raise

    def tearDown(self):
        super().tearDown()
        self.device.shutdownDevice()

    def testOutletCount(self):
        self.assertEqual(self.device.outletCount, 3)

    def testTurnOutletOnAndOff(self):
        self.device.turnOutletOn(1)
        self.assertTrue(self.device.isOutletOn(1))
        self.device.turnOutletOff(1)
        self.assertFalse(self.device.isOutletOn(1))

    def testDeviceType(self):
        self.assertIn(self.device.deviceType(),
                      ("Basic", "Digital IO", "Watchdog", "Smart", "Unknown"))


if __name__ == '__main__':
    unittest.main()
