import env
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.sources.millennia import MillenniaDevice, DebugMillenniaDevice
from hardwarelibrary.sources.capabilities import (
    OnOffControl, ShutterControl, PowerControl, InterlockControl, WavelengthControl)
from hardwarelibrary.sources.lasersourcedevice import LaserSourceDevice

# Set to the serial port of an attached Millennia eV to exercise TestMillenniaDevice;
# the tests skip when no laser answers there.
MILLENNIA_PORT = "/dev/cu.usbserial-MILLENNIA"


class TestDebugMillenniaDevice(unittest.TestCase):
    def setUp(self):
        self.laser = DebugMillenniaDevice()
        self.laser.initializeDevice()

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testIsLaserSourceWithOnOffShutterAndPowerCapabilities(self):
        self.assertIsInstance(self.laser, LaserSourceDevice)
        self.assertIsInstance(self.laser, OnOffControl)
        self.assertIsInstance(self.laser, ShutterControl)
        self.assertIsInstance(self.laser, PowerControl)

    def testAdvertisesOnOffShutterAndPower(self):
        self.assertEqual(set(self.laser.capabilities()),
                         {OnOffControl, ShutterControl, PowerControl})

    def testDoesNotAdvertiseUnsupportedCapabilities(self):
        for unsupported in (InterlockControl, WavelengthControl):
            self.assertFalse(self.laser.hasCapability(unsupported))

    def testStartsOffWithShutterClosed(self):
        self.assertFalse(self.laser.isLaserOn())
        self.assertFalse(self.laser.isShutterOpen())

    def testTurnOnOffRoundTrip(self):
        self.laser.turnOn()
        self.assertTrue(self.laser.isLaserOn())
        self.laser.turnOff()
        self.assertFalse(self.laser.isLaserOn())

    def testShutterOpenCloseRoundTrip(self):
        self.laser.openShutter()
        self.assertTrue(self.laser.isShutterOpen())
        self.laser.closeShutter()
        self.assertFalse(self.laser.isShutterOpen())

    def testSetAndReadPowerRoundTrip(self):
        self.laser.setPower(4.95)
        self.assertAlmostEqual(self.laser.power(), 4.95, places=2)

    def testRejectsPowerBelowMinimum(self):
        with self.assertRaises(ValueError):
            self.laser.setPower(0.0)

    def testRejectsPowerAboveMaximum(self):
        with self.assertRaises(ValueError):
            self.laser.setPower(30.0)

    def testAcceptsPowerAtBoundaries(self):
        self.laser.setPower(self.laser.minPower)
        self.assertAlmostEqual(self.laser.power(), self.laser.minPower, places=2)
        self.laser.setPower(self.laser.maxPower)
        self.assertAlmostEqual(self.laser.power(), self.laser.maxPower, places=2)

    def testInitializeReadsAndParsesIdentity(self):
        self.assertEqual(self.laser.manufacturer, "Spectra Physics")
        self.assertEqual(self.laser.model, "Millennia eV 25S")
        self.assertEqual(self.laser.firmwareVersion, "SW214-00.004.096")
        self.assertEqual(self.laser.laserSerialNumber, "3239")

    def testShutterIsIndependentOfOnOff(self):
        self.laser.turnOn()
        self.assertTrue(self.laser.isLaserOn())
        self.assertFalse(self.laser.isShutterOpen())  # on, but still blocked

        self.laser.openShutter()
        self.assertTrue(self.laser.isLaserOn())
        self.assertTrue(self.laser.isShutterOpen())

        self.laser.turnOff()
        self.assertFalse(self.laser.isLaserOn())
        self.assertTrue(self.laser.isShutterOpen())  # off, shutter unchanged


class TestMillenniaDevice(unittest.TestCase):
    def setUp(self):
        self.laser = MillenniaDevice(portPath=MILLENNIA_PORT)
        try:
            self.laser.initializeDevice()
        except PhysicalDevice.UnableToInitialize:
            self.skipTest("No Millennia eV reachable at {0}".format(MILLENNIA_PORT))

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testReadsOnOffState(self):
        self.assertIn(self.laser.isLaserOn(), (True, False))

    def testReadsShutterState(self):
        self.assertIn(self.laser.isShutterOpen(), (True, False))

    def testReadsPower(self):
        self.assertIsInstance(self.laser.power(), float)

    def testReadsIdentity(self):
        self.assertIsNotNone(self.laser.idn)
        self.assertIn("Millennia", self.laser.idn)


if __name__ == "__main__":
    unittest.main()
