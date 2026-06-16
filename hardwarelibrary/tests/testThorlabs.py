import env
import unittest

from hardwarelibrary.motion.thorlabs import (
    ThorlabsDevice, ThorlabsFTDIDevice, ThorlabsKinesisDevice)
from hardwarelibrary.motion.linearmotiondevice import LinearMotionDevice


class TestThorlabsDeviceFactory(unittest.TestCase):
    def testBackendsSubclassThorlabsDevice(self):
        self.assertTrue(issubclass(ThorlabsFTDIDevice, ThorlabsDevice))
        self.assertTrue(issubclass(ThorlabsKinesisDevice, ThorlabsDevice))

    def testThorlabsDeviceIsALinearMotionDevice(self):
        self.assertTrue(issubclass(ThorlabsDevice, LinearMotionDevice))

    def testBackendPreferenceOrder(self):
        self.assertEqual(ThorlabsDevice.backendClasses(),
                         [ThorlabsFTDIDevice, ThorlabsKinesisDevice])

    def testFTDIBackendIsAvailableForDebug(self):
        self.assertTrue(ThorlabsFTDIDevice.isAvailable("debug"))

    def testKinesisIsAvailableReturnsBool(self):
        self.assertIsInstance(ThorlabsKinesisDevice.isAvailable(), bool)

    def testFirstAvailableBackendForDebugIsFTDI(self):
        self.assertIs(ThorlabsDevice.firstAvailableBackend("debug"), ThorlabsFTDIDevice)

    def testFactoryRoutesDebugToFTDIBackend(self):
        device = ThorlabsDevice("debug")
        self.assertIs(type(device), ThorlabsFTDIDevice)
        self.assertIsInstance(device, ThorlabsDevice)
        self.assertIsInstance(device, LinearMotionDevice)

    def testFactoryReturnsInitializedBackend(self):
        device = ThorlabsDevice("debug")
        # __init__ ran once on the backend (these are set in its __init__)
        self.assertEqual(device.nativeStepsPerMicrons, 16)
        self.assertEqual(device.xMaxLimit, 25000 * 16)

    def testDirectBackendConstructionIsNotRerouted(self):
        device = ThorlabsFTDIDevice("debug")
        self.assertIs(type(device), ThorlabsFTDIDevice)


class TestThorlabsFTDIDebugMovement(unittest.TestCase):
    """Exercise the native APT binary protocol over the built-in DebugSerialPort,
    so the FTDI command/reply path runs without a connected stage."""

    def setUp(self):
        self.device = ThorlabsFTDIDevice("debug")
        self.device.initializeDevice()

    def tearDown(self):
        if self.device.port is not None:
            self.device.shutdownDevice()

    def testInitialPositionIsZero(self):
        self.assertEqual(self.device.position(), (0, 0, 0))

    def testMoveToSetsPosition(self):
        self.device.moveTo((160, 320, 480))
        self.assertEqual(self.device.position(), (160, 320, 480))

    def testMoveByIsRelativeToCurrentPosition(self):
        self.device.moveTo((100, 200, 300))
        self.device.moveBy((10, 20, 30))
        self.assertEqual(self.device.position(), (110, 220, 330))

    def testHomeResetsToZero(self):
        self.device.moveTo((160, 320, 480))
        self.device.home()
        self.assertEqual(self.device.position(), (0, 0, 0))

    def testPositionInMicronsUsesNativeStepsPerMicrons(self):
        self.device.moveTo((160, 320, 480))
        self.assertEqual(self.device.positionInMicrons(), (10, 20, 30))

    def testMoveInMicronsToConvertsToMicrosteps(self):
        self.device.moveInMicronsTo((10, 20, 30))
        self.assertEqual(self.device.position(), (160, 320, 480))

    def testShutdownClearsPort(self):
        self.device.shutdownDevice()
        self.assertIsNone(self.device.port)

    def testCommandAfterShutdownReinitializesPort(self):
        self.device.shutdownDevice()
        # sendCommandBytes() re-initializes when the port is gone; the debug
        # port starts back at the origin.
        self.device.moveTo((16, 32, 48))
        self.assertEqual(self.device.position(), (16, 32, 48))


if __name__ == "__main__":
    unittest.main()
