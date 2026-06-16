import env
import os
import unittest

try:
    import Pyro5  # noqa: F401
    HAVE_PYRO5 = True
except Exception:
    HAVE_PYRO5 = False


@unittest.skipUnless(HAVE_PYRO5, "Pyro5 not installed (optional 'remote' extra)")
class TestRemotableDeviceInSeparateProcess(unittest.TestCase):
    """Drive a Remotable device running in a separate, supervised process through
    the generic ProxyDevice handle, and verify automatic forwarding and fault
    isolation. The device serves itself (Remotable mixin); no servant, no mirror."""

    def setUp(self):
        from hardwarelibrary.remoting import launchIsolatedDevice
        from hardwarelibrary.remoting.exampledevices import RemotableDebugStage
        self.stage = launchIsolatedDevice(RemotableDebugStage)

    def tearDown(self):
        try:
            self.stage.shutdownProcess()
        except Exception:
            pass

    def testRunsInItsOwnProcess(self):
        self.assertTrue(self.stage.isAlive())
        self.assertNotEqual(self.stage.processId, os.getpid())

    def testMethodsForwardAutomatically(self):
        # None of these are declared on ProxyDevice; they forward generically.
        self.stage.initializeDevice()
        self.assertEqual(tuple(self.stage.position()), (0, 0, 0))
        self.stage.moveTo((160, 320, 480))
        self.assertEqual(tuple(self.stage.position()), (160, 320, 480))
        self.stage.moveBy((10, 20, 30))
        self.assertEqual(tuple(self.stage.position()), (170, 340, 510))
        self.stage.home()
        self.assertEqual(tuple(self.stage.position()), (0, 0, 0))

    def testCommonAttributesReadLiveFromRemote(self):
        from hardwarelibrary.physicaldevice import DeviceState
        self.assertEqual(self.stage.serialNumber, "debug")
        self.stage.initializeDevice()
        self.assertIsInstance(self.stage.state, DeviceState)
        self.assertEqual(self.stage.state, DeviceState.Ready)

    def testProcessDeathIsIsolatedFromCaller(self):
        from hardwarelibrary.remoting import IsolatedDeviceError
        self.stage.initializeDevice()
        # Simulate a buggy driver taking down its own process mid-session.
        self.stage._process.kill()
        self.stage._process.wait(timeout=5)

        self.assertFalse(self.stage.isAlive())
        with self.assertRaises(IsolatedDeviceError):
            self.stage.position()
        # The caller (this test process) is unaffected and keeps running.
        self.assertEqual(2 + 2, 4)


@unittest.skipUnless(HAVE_PYRO5, "Pyro5 not installed (optional 'remote' extra)")
class TestInProcessRemotableDevice(unittest.TestCase):
    """The same Remotable class, created in-process, is the real device."""

    def testInProcessIsTheRealDevice(self):
        from hardwarelibrary.remoting import createDevice
        from hardwarelibrary.remoting.exampledevices import RemotableDebugStage
        from hardwarelibrary.motion.linearmotiondevice import LinearMotionDevice

        device = createDevice(RemotableDebugStage, isolated=False)
        self.assertIsInstance(device, LinearMotionDevice)  # real device: isinstance holds
        device.initializeDevice()
        device.moveTo((1, 2, 3))
        self.assertEqual(device.position(), (1, 2, 3))
        device.shutdownDevice()


if __name__ == "__main__":
    unittest.main()
