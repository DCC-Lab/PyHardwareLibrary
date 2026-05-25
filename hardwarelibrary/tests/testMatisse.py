import env
import unittest

from hardwarelibrary.sources.matisse import MatisseDevice, DebugMatisseDevice
from hardwarelibrary.sources.capabilities import WavelengthControl
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState

MATISSE_HOST = "172.16.8.57"
MATISSE_PORT = 30000


class TestDebugMatisseDevice(unittest.TestCase):
    def setUp(self):
        self.matisse = DebugMatisseDevice()
        self.matisse.initializeDevice()

    def tearDown(self):
        self.matisse.shutdownDevice()

    def testIsPhysicalDeviceWithWavelengthCapability(self):
        self.assertIsInstance(self.matisse, PhysicalDevice)
        self.assertIsInstance(self.matisse, WavelengthControl)

    def testInitializeReadsIdn(self):
        self.assertEqual(self.matisse.state, DeviceState.Ready)
        self.assertIn("Matisse", self.matisse.idn)

    def testBifiWavelengthRoundTrip(self):
        self.matisse.setBifiWavelength(782.5)
        self.assertAlmostEqual(self.matisse.bifiWavelength(), 782.5, places=4)

    def testBifiPositionRoundTrip(self):
        self.matisse.setBifiPosition(123456)
        self.assertEqual(self.matisse.bifiPosition(), 123456)

    def testWavelengthCapabilityDrivesBifi(self):
        self.matisse.setWavelength(805.0)
        self.assertAlmostEqual(self.matisse.wavelength(), 805.0, places=4)
        self.assertAlmostEqual(self.matisse.bifiWavelength(), 805.0, places=4)

    def testWavelengthRangeIsTheConfiguredRange(self):
        self.assertEqual(self.matisse.wavelengthRange(), (700.0, 1000.0))

    def testThinEtalonLockToggles(self):
        self.assertFalse(self.matisse.thinEtalonLockIsOn())
        self.matisse.setThinEtalonLock(True)
        self.assertTrue(self.matisse.thinEtalonLockIsOn())
        self.matisse.setThinEtalonLock(False)
        self.assertFalse(self.matisse.thinEtalonLockIsOn())

    def testThinEtalonErrorSignalFallsBackWhenCommandAbsent(self):
        # fw 1.20 has no TE:CNTRERR; value is setpoint - reflex/resonator.
        expected = 0.5 - 0.42 / 0.45
        self.assertAlmostEqual(self.matisse.thinEtalonErrorSignal(), expected, places=6)

    def testPiezoEtalonAmplitudeRoundTrip(self):
        self.matisse.setPiezoEtalonAmplitude(0.0123)
        self.assertAlmostEqual(self.matisse.piezoEtalonAmplitude(), 0.0123, places=6)

    def testPiezoEtalonPhaseRoundTrip(self):
        self.matisse.setPiezoEtalonPhase(42)
        self.assertEqual(self.matisse.piezoEtalonPhase(), 42)

    def testSlowPiezoSetpointRoundTrip(self):
        self.matisse.setSlowPiezoSetpoint(0.321)
        self.assertAlmostEqual(self.matisse.slowPiezoSetpoint(), 0.321, places=6)

    def testFastPiezoLockReadsBoolean(self):
        self.assertFalse(self.matisse.fastPiezoIsLocked())

    def testScanLimitsRoundTrip(self):
        self.matisse.setScanLowerLimit(0.2)
        self.matisse.setScanUpperLimit(0.8)
        self.assertAlmostEqual(self.matisse.scanLowerLimit(), 0.2, places=6)
        self.assertAlmostEqual(self.matisse.scanUpperLimit(), 0.8, places=6)

    def testScanDeviceRoundTrip(self):
        self.matisse.setScanDevice(2)
        self.assertEqual(self.matisse.scanDevice(), 2)

    def testBifiNotMovingWhenIdle(self):
        self.assertFalse(self.matisse.bifiIsMoving())

    def testWaitTimesOutWhileMoving(self):
        self.matisse.registers["MOTBI:STA"] = str(MatisseDevice.movingStatusBit | 0x02)
        self.assertTrue(self.matisse.bifiIsMoving())
        with self.assertRaises(MatisseDevice.MotionTimeout):
            self.matisse.waitForBifi(timeout=0.1)


class TestMatisseDevice(unittest.TestCase):
    def setUp(self):
        self.matisse = MatisseDevice(MATISSE_HOST, MATISSE_PORT)
        try:
            self.matisse.initializeDevice()
        except PhysicalDevice.UnableToInitialize:
            self.skipTest("No Matisse Commander reachable at {0}:{1}".format(MATISSE_HOST, MATISSE_PORT))

    def tearDown(self):
        if self.matisse.state == DeviceState.Ready:
            self.matisse.shutdownDevice()

    def testIdentifiesAsMatisse(self):
        self.assertIn("Matisse", self.matisse.idn)

    def testReadsBifiWavelengthInRange(self):
        wavelength = self.matisse.bifiWavelength()
        self.assertGreater(wavelength, 600.0)
        self.assertLess(wavelength, 1100.0)

    def testReadsEveryTuningElementWithoutError(self):
        self.matisse.bifiPosition()
        self.matisse.thinEtalonPosition()
        self.matisse.thinEtalonReflexPower()
        self.matisse.thinEtalonErrorSignal()
        self.matisse.piezoEtalonBaseline()
        self.matisse.slowPiezoValue()
        self.matisse.fastPiezoValue()
        self.matisse.scanValue()


if __name__ == "__main__":
    unittest.main()
