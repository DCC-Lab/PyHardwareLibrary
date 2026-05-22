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


if __name__ == "__main__":
    unittest.main()
