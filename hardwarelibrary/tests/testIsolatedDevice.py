import env
import os
import unittest

try:
    import Pyro5  # noqa: F401
    HAVE_PYRO5 = True
except Exception:
    HAVE_PYRO5 = False


@unittest.skipUnless(HAVE_PYRO5, "Pyro5 not installed (optional 'remote' extra)")
class TestIsolatedDevice(unittest.TestCase):
    """Drive a DebugLinearMotionDevice running in a separate, supervised process
    through the same-interface RemoteDevice proxy, and verify fault isolation."""

    def setUp(self):
        from hardwarelibrary.remoting import launchIsolatedDevice
        from hardwarelibrary.motion.linearmotiondevice import DebugLinearMotionDevice
        self.device = launchIsolatedDevice(DebugLinearMotionDevice)

    def tearDown(self):
        try:
            self.device.shutdownProcess()
        except Exception:
            pass

    def testRunsInItsOwnProcess(self):
        self.assertTrue(self.device.isAlive())
        self.assertNotEqual(self.device.processId, os.getpid())

    def testDriveThroughProxyMatchesLocalInterface(self):
        self.device.initializeDevice()
        self.assertEqual(self.device.position(), (0, 0, 0))
        self.device.moveTo((160, 320, 480))
        self.assertEqual(self.device.position(), (160, 320, 480))
        self.device.moveBy((10, 20, 30))
        self.assertEqual(self.device.position(), (170, 340, 510))
        self.device.home()
        self.assertEqual(self.device.position(), (0, 0, 0))

    def testStateRoundTripsAsDeviceState(self):
        from hardwarelibrary.physicaldevice import DeviceState
        self.device.initializeDevice()
        self.assertIsInstance(self.device.state, DeviceState)
        self.assertEqual(self.device.state, DeviceState.Ready)

    def testIdentityAccessors(self):
        self.assertEqual(self.device.serialNumber, "debug")
        self.assertIsInstance(self.device.idVendor, int)
        self.assertIsInstance(self.device.idProduct, int)

    def testProcessDeathIsIsolatedFromCaller(self):
        from hardwarelibrary.remoting import IsolatedDeviceError
        self.device.initializeDevice()
        # Simulate a buggy driver taking down its own process mid-session.
        self.device._process.kill()
        self.device._process.wait(timeout=5)

        self.assertFalse(self.device.isAlive())
        with self.assertRaises(IsolatedDeviceError):
            self.device.position()
        # The caller (this test process) is unaffected and keeps running.
        self.assertEqual(2 + 2, 4)


if __name__ == "__main__":
    unittest.main()
