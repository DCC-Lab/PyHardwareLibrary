import env  # noqa: F401  (sets sys.path)
import time
import unittest
from threading import Lock

from hardwarelibrary.devicecontroller import (
    DeviceController, DeviceControllerNotification, connection_error_reason)
from hardwarelibrary.notificationcenter import NotificationCenter
from hardwarelibrary.sources.millennia import DebugMillenniaDevice


class FlakyMillennia(DebugMillenniaDevice):
    """A debug Millennia that can be taken 'offline' to simulate a dropped link."""

    def __init__(self):
        super().__init__()
        self.online = True

    def doInitializeDevice(self):
        if not self.online:
            raise IOError("port gone")
        return super().doInitializeDevice()

    def doGetStatusUserInfo(self):
        if not self.online:
            raise IOError("[Errno 16] Resource busy: link down")
        return super().doGetStatusUserInfo()


class NoStatusDevice(DebugMillenniaDevice):
    """A debug device that exposes no status snapshot."""

    def doGetStatusUserInfo(self):
        return None


class Recorder:
    """Collects a controller's notifications for assertions."""

    def __init__(self, controller):
        self.events = []
        self._lock = Lock()
        self._nc = NotificationCenter()
        for name in DeviceControllerNotification:
            self._nc.addObserver(self, self._handle, name, observedObject=controller)

    def _handle(self, notification):
        with self._lock:
            self.events.append((notification.name, notification.userInfo))

    def names(self):
        with self._lock:
            return [name for name, _ in self.events]

    def wait_for(self, name, timeout=3.0):
        """Wait for a notification and return its userInfo (which may be None)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                for nm, info in self.events:
                    if nm == name:
                        return info
            time.sleep(0.02)
        return None

    def wait_seen(self, name, timeout=3.0):
        """Wait for a notification to arrive; return True/False (payload-agnostic)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if name in self.names():
                return True
            time.sleep(0.02)
        return False

    def last_status(self):
        with self._lock:
            for nm, info in reversed(self.events):
                if nm == DeviceControllerNotification.status:
                    return info
        return None

    def remove(self):
        self._nc.removeObserver(self)


class TestDeviceController(unittest.TestCase):
    def setUp(self):
        self.controllers = []
        self.recorders = []

    def tearDown(self):
        for controller in self.controllers:
            controller.stop()
        for recorder in self.recorders:
            recorder.remove()

    def make(self, device=None, **kwargs):
        device = device or DebugMillenniaDevice()
        kwargs.setdefault("poll_interval", 0.2)
        kwargs.setdefault("reconnect_interval", 0.3)
        controller = DeviceController(device, **kwargs)
        recorder = Recorder(controller)
        self.controllers.append(controller)
        self.recorders.append(recorder)
        controller.start()
        return controller, recorder

    # -- connection + status --

    def testConnectPostsDidConnectAndStatus(self):
        controller, rec = self.make()
        controller.connect()
        self.assertIsNotNone(rec.wait_for(DeviceControllerNotification.didConnect))
        status = rec.wait_for(DeviceControllerNotification.status)
        self.assertIsNotNone(status)
        self.assertEqual(set(status), {"power", "isLaserOn", "isShutterOpen"})
        self.assertTrue(controller.is_connected)

    def testSubmittedCommandRunsAndStatusReflectsIt(self):
        controller, rec = self.make()
        controller.connect()
        rec.wait_for(DeviceControllerNotification.didConnect)
        controller.submit(lambda device: device.turnOn())
        controller.submit(lambda device: device.openShutter())
        deadline = time.time() + 3.0
        while time.time() < deadline:
            status = rec.last_status()
            if status and status["isLaserOn"] and status["isShutterOpen"]:
                break
            time.sleep(0.05)
        self.assertTrue(status["isLaserOn"])
        self.assertTrue(status["isShutterOpen"])

    def testFailedCommandPostsCommandFailed(self):
        controller, rec = self.make()
        controller.connect()
        rec.wait_for(DeviceControllerNotification.didConnect)

        def boom(device):
            raise ValueError("nope")

        controller.submit(boom)
        info = rec.wait_for(DeviceControllerNotification.commandFailed)
        self.assertIsInstance(info, ValueError)

    def testCommandWhileDisconnectedFails(self):
        controller, rec = self.make()
        controller.submit(lambda device: device.turnOn())
        info = rec.wait_for(DeviceControllerNotification.commandFailed)
        self.assertIsInstance(info, RuntimeError)

    # -- drop / reconnect --

    def testConnectionLostThenAutoReconnect(self):
        device = FlakyMillennia()
        controller, rec = self.make(device=device)
        controller.connect()
        rec.wait_for(DeviceControllerNotification.didConnect)

        device.online = False
        self.assertIsNotNone(
            rec.wait_for(DeviceControllerNotification.connectionLost),
            "should report the drop")
        self.assertFalse(controller.is_connected)

        # Count reconnects so we can confirm a *new* one after recovery.
        before = rec.names().count(DeviceControllerNotification.didConnect)
        device.online = True
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if (rec.names().count(DeviceControllerNotification.didConnect) > before
                    and controller.is_connected):
                break
            time.sleep(0.05)
        self.assertTrue(controller.is_connected, "should have auto-reconnected")

    def testExplicitDisconnectDoesNotReconnect(self):
        controller, rec = self.make()
        controller.connect()
        rec.wait_for(DeviceControllerNotification.didConnect)
        controller.disconnect()
        self.assertTrue(rec.wait_seen(DeviceControllerNotification.didDisconnect))
        time.sleep(0.8)  # longer than a couple of reconnect intervals
        self.assertFalse(controller.is_connected)

    def testNoAutoReconnectGivesUpAfterDrop(self):
        device = FlakyMillennia()
        controller, rec = self.make(device=device, auto_reconnect=False)
        controller.connect()
        rec.wait_for(DeviceControllerNotification.didConnect)
        device.online = False
        rec.wait_for(DeviceControllerNotification.connectionLost)
        before = rec.names().count(DeviceControllerNotification.didConnect)
        device.online = True
        time.sleep(1.0)
        self.assertEqual(
            rec.names().count(DeviceControllerNotification.didConnect), before,
            "must not reconnect when auto_reconnect is False")

    # -- misc --

    def testDeviceWithoutStatusStillConnects(self):
        controller, rec = self.make(device=NoStatusDevice())
        controller.connect()
        self.assertIsNotNone(rec.wait_for(DeviceControllerNotification.didConnect))
        time.sleep(0.6)
        self.assertNotIn(DeviceControllerNotification.status, rec.names())

    def testConnectionErrorReasonClassifiesChain(self):
        cause = OSError("[Errno 16] Resource busy: '/dev/cu.x'")
        wrapper = RuntimeError("could not initialize")
        wrapper.__cause__ = cause
        self.assertEqual(connection_error_reason(wrapper), "busy")
        self.assertIsNone(connection_error_reason(RuntimeError("weird")))


if __name__ == "__main__":
    unittest.main()
