import env # modifies path
import unittest
import time
from threading import Thread, RLock
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.motion import DebugLinearMotionDevice, LinearMotionDevice
from hardwarelibrary.motion import SutterDevice
from hardwarelibrary.communication.diagnostics import *
from hardwarelibrary.devicemanager import DeviceManager, DeviceManagerNotification

class TestDeviceManager(unittest.TestCase):

    def testIsRunning(self):
        self.assertTrue(True)

    def testInstantiate(self):
        self.assertIsNotNone(DeviceManager())

    def testSingleton(self):
        dm1 = DeviceManager()
        dm2 = DeviceManager()
        self.assertEqual(dm1, dm2)

    def testEmpty(self):
        self.assertEqual(len(DeviceManager().devices), 0)

    def testClassTypes(self):
        device = DebugLinearMotionDevice()
        self.assertTrue( isinstance(device, DebugLinearMotionDevice))
        self.assertTrue( isinstance(device, LinearMotionDevice))
        self.assertTrue( issubclass(type(device), PhysicalDevice))
        self.assertTrue( issubclass(type(device), LinearMotionDevice))
        self.assertTrue( issubclass(type(device), DebugLinearMotionDevice))

    def setUp(self):
        # DeviceManager().devices = []
        dm = DeviceManager()
        DeviceManager._instance = None
        del(dm)
        self.lock = RLock()
        self.notificationsToReceive = []
        self.assertEqual(NotificationCenter().observersCount(), 0)

    def tearDown(self):
        self.assertEqual(NotificationCenter().observersCount(), 0)

    def testMatching1(self):
        dm = DeviceManager()
        device = DebugLinearMotionDevice()
        dm.addDevice(device)

        matched = dm.matchPhysicalDevicesOfType(DebugLinearMotionDevice)
        self.assertTrue(len(matched) == 1)
        self.assertTrue(matched[0] == device)

    def testMatching2(self):
        dm = DeviceManager()
        device1 = DebugLinearMotionDevice()
        device2 = DebugLinearMotionDevice()
        dm.addDevice(device1)
        dm.addDevice(device2)

        matched = dm.matchPhysicalDevicesOfType(DebugLinearMotionDevice)
        self.assertTrue(len(matched) == 2)

    def testMatching3WithSerial(self):
        dm = DeviceManager()
        device1 = DebugLinearMotionDevice()
        device2 = DebugLinearMotionDevice()
        device2.serialNumber = "debug2"
        dm.addDevice(device1)
        dm.addDevice(device2)

        matched = dm.matchPhysicalDevicesOfType(DebugLinearMotionDevice, serialNumber="debug")
        self.assertTrue(len(matched) == 2)

        matched = dm.matchPhysicalDevicesOfType(DebugLinearMotionDevice, serialNumber="debu")
        self.assertTrue(len(matched) == 2)

        matched = dm.matchPhysicalDevicesOfType(DebugLinearMotionDevice, serialNumber="debug2")
        self.assertTrue(len(matched) == 1)

    def testMatching4WithSubclass(self):
        dm = DeviceManager()
        device1 = DebugLinearMotionDevice()
        dm.addDevice(device1)
        device2 = SutterDevice("debug")
        dm.addDevice(device2)

        matched = dm.matchPhysicalDevicesOfType(LinearMotionDevice)
        self.assertTrue(len(matched) == 2)
        self.assertTrue(device1 in matched )
        self.assertTrue(device2 in matched )

        matched = dm.matchPhysicalDevicesOfType(DebugLinearMotionDevice)
        self.assertTrue(len(matched) == 1)
        self.assertTrue(device1 in matched )

        matched = dm.matchPhysicalDevicesOfType(SutterDevice)
        self.assertTrue(len(matched) == 1)
        self.assertTrue(device2 in matched )

    def testStartRunLoop(self):
        dm = DeviceManager()
        dm.startMonitoring()
        startTime = time.time()
        expectedMaxEndTime = startTime + 3.0
        time.sleep(2.0)
        self.assertEqual(len(dm.devices), 1)
        dm.stopMonitoring()
        self.assertTrue(expectedMaxEndTime > time.time() )
        self.assertEqual(len(dm.devices), 0)

    def testRestartRunLoop(self):
        dm = DeviceManager()

        startTime = time.time()
        expectedMaxEndTime = startTime + 1.0
        dm.startMonitoring()
        dm.stopMonitoring()
        self.assertTrue(expectedMaxEndTime > time.time() )

        startTime = time.time()
        expectedMaxEndTime = startTime + 1.0
        dm.startMonitoring()
        dm.stopMonitoring()
        self.assertTrue(expectedMaxEndTime > time.time() )

    def testStartRunLoopTwice(self):
        dm = DeviceManager()
        dm.startMonitoring()
        with self.assertRaises(Exception):
            dm.startMonitoring()
        dm.stopMonitoring()

    def testStopRunLoopTwice(self):
        dm = DeviceManager()
        with self.assertRaises(Exception):
            dm.stopMonitoring()

    def testNotificationReceived(self):
        dm = DeviceManager()
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, DeviceManagerNotification.willStartMonitoring)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didStartMonitoring)
        nc.addObserver(self, self.handle, DeviceManagerNotification.willStopMonitoring)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didStopMonitoring)
        nc.addObserver(self, self.handleStatus, DeviceManagerNotification.status)
        self.notificationsToReceive = [DeviceManagerNotification.willStartMonitoring,
                                       DeviceManagerNotification.didStartMonitoring,
                                       DeviceManagerNotification.willStopMonitoring,
                                       DeviceManagerNotification.didStopMonitoring]

        dm.startMonitoring()
        time.sleep(0.5)
        dm.stopMonitoring()

        self.assertTrue(len(self.notificationsToReceive) == 0)        
        nc.removeObserver(self)
        self.assertEqual(nc.observersCount(), 0)

    def testNotificationReceivedWhileAddingDevices(self):
        dm = DeviceManager()
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, DeviceManagerNotification.willStartMonitoring)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didStartMonitoring)
        nc.addObserver(self, self.handle, DeviceManagerNotification.willStopMonitoring)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didStopMonitoring)
        nc.addObserver(self, self.handleStatus, DeviceManagerNotification.status)
        self.notificationsToReceive = [DeviceManagerNotification.willStartMonitoring,
                                       DeviceManagerNotification.didStartMonitoring,
                                       DeviceManagerNotification.willStopMonitoring,
                                       DeviceManagerNotification.didStopMonitoring]

        dm.startMonitoring()
        time.sleep(0.5)
        self.addRemoveManyDevices()
        time.sleep(0.5)
        dm.stopMonitoring()

        self.assertTrue(len(self.notificationsToReceive) == 0)        
        nc.removeObserver(self)

    def testNotificationReceivedFromAddingDevices(self):
        dm = DeviceManager()
        nc = NotificationCenter()
        dm.startMonitoring()
        time.sleep(1.0) # let newlyConnected devices be added.
        nc.addObserver(self, self.handle, DeviceManagerNotification.willAddDevice)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didAddDevice)
        nc.addObserver(self, self.handle, DeviceManagerNotification.willRemoveDevice)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didRemoveDevice)

        self.notificationsToReceive = [DeviceManagerNotification.willAddDevice,DeviceManagerNotification.didAddDevice]*1000
        self.notificationsToReceive.extend([DeviceManagerNotification.willRemoveDevice,DeviceManagerNotification.didRemoveDevice]*1000)


        time.sleep(0.5)
        self.addRemoveManyDevices(1000)
        time.sleep(0.5)
        dm.stopMonitoring()

        with self.lock:
            self.assertTrue(len(self.notificationsToReceive) == 0)        
        nc.removeObserver(self)

    # def testNewlyConnectedDevices(self):
    #     dm = DeviceManager()
    #     self.assertTrue(len(dm.newlyConnectedUSBDevices()) > 4)

    def addRemoveManyDevices(self, N=1000):
        dm = DeviceManager()
        devices = []
        for i in range(N):
            device = DebugLinearMotionDevice()
            dm.addDevice(device)
            devices.append(device)

        for device in devices:
            dm.removeDevice(device)

    def handle(self, notification):
        with self.lock:
            self.assertEqual(notification.name, self.notificationsToReceive[0])
            self.notificationsToReceive.pop(0)

    def handleStatus(self, notification):
        with self.lock:
            devices = notification.userInfo
        # if len(devices) != 0:
        #     self.assertTrue(isinstance(devices[0], DebugLinearMotionDevice))

if __name__ == '__main__':
    unittest.main()
