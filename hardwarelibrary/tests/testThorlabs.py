import env
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.motion.thorlabs import ThorlabsDevice, ThorlabsKinesisDevice
from hardwarelibrary.motion.linearmotiondevice import LinearMotionDevice


class TestThorlabsDeviceFactory(unittest.TestCase):
    def testKinesisSubclassesThorlabsDevice(self):
        self.assertTrue(issubclass(ThorlabsKinesisDevice, ThorlabsDevice))

    def testThorlabsDeviceIsALinearMotionDevice(self):
        self.assertTrue(issubclass(ThorlabsDevice, LinearMotionDevice))

    def testKinesisIsTheOnlyBackend(self):
        self.assertEqual(ThorlabsDevice.backendClasses(), [ThorlabsKinesisDevice])

    def testKinesisIsAvailableReturnsBool(self):
        self.assertIsInstance(ThorlabsKinesisDevice.isAvailable(), bool)

    def testKinesisDeviceIsConcrete(self):
        # Every LinearMotionDevice hook (doMoveTo/doMoveBy/doGetPosition/doHome,
        # plus doInitializeDevice/doShutdownDevice) must be implemented, or the
        # class cannot be instantiated. Guards against the missing-doMoveBy bug.
        self.assertEqual(ThorlabsKinesisDevice.__abstractmethods__, frozenset())

    def testFirstAvailableBackendMatchesAvailability(self):
        # The result depends on whether pylablib/Kinesis is installed here, so
        # assert the behaviour for whichever case applies rather than the env.
        if ThorlabsKinesisDevice.isAvailable():
            self.assertIs(ThorlabsDevice.firstAvailableBackend(), ThorlabsKinesisDevice)
        else:
            with self.assertRaises(PhysicalDevice.UnableToInitialize):
                ThorlabsDevice.firstAvailableBackend()


if __name__ == "__main__":
    unittest.main()
