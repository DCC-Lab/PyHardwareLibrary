import env # modifies path
import unittest
import time
import re
from enum import Enum
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.motion import DebugLinearMotionDevice, LinearMotionDevice
from hardwarelibrary.motion import SutterDevice
from threading import Thread, RLock
from hardwarelibrary.communication.diagnostics import *

class DeviceManagerNotification(Enum):
    status              = "status"
    willStartMonitoring = "willStartMonitoring"
    didStartMonitoring  = "didStartMonitoring"
    willStopMonitoring  = "willStopMonitoring"
    didStopMonitoring   = "didStopMonitoring"

    willAddDevice       = "willAddDevice"
    didAddDevice        = "didAddDevice"
    willRemoveDevice    = "willRemoveDevice"
    didRemoveDevice     = "didRemoveDevice"

class DebugPhysicalDevice(PhysicalDevice):
    def __init__(self):
        super().__init__("debug", 0xffff, 0xfffe)
        self.errorInitialize = False
        self.errorShutdown = False

    def doInitializeDevice(self):
        if self.errorInitialize:
            raise RuntimeError()

    def doShutdownDevice(self):
        if self.errorShutdown:
            raise RuntimeError()

class DeviceManager:
    _instance = None

    def __init__(self):
        if not hasattr(self, 'devices'):
            self.devices = set()
        if not hasattr(self, 'quitMonitoring'):
            self.quitMonitoring = False
        if not hasattr(self, 'lock'):
            self.lock = RLock()
        if not hasattr(self, 'monitoring'):
            self.monitoring = None
        if not hasattr(self, 'usbDevices'):
            self.usbDevices = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def startMonitoring(self):
        with self.lock:
            if not self.isMonitoring:
                self.quitMonitoring = False
                self.monitoring = Thread(target=self.monitoringLoop, name="DeviceManager-RunLoop")
                NotificationCenter().postNotification(notificationName=DeviceManagerNotification.willStartMonitoring, notifyingObject=self)
                self.monitoring.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    def monitoringLoop(self):        
        startTime = time.time()
        endTime = startTime + 5.0
        NotificationCenter().postNotification(DeviceManagerNotification.didStartMonitoring, notifyingObject=self)
        while time.time() < endTime :
            self.lookForNewlyConnectedDevices()
            # self.lookForNewlyDisconnectedDevices()

            currentDevices = []
            with self.lock:
                currentDevices.extend(self.devices)

            NotificationCenter().postNotification(DeviceManagerNotification.status, notifyingObject=self, userInfo=currentDevices)

            with self.lock:
                if self.quitMonitoring:
                     break
            time.sleep(0.2)
        NotificationCenter().postNotification(DeviceManagerNotification.didStopMonitoring, notifyingObject=self)

    def newlyConnectedUSBDevices(self):
        currentlyConnectedDevices = connectedUSBDevices()
        newlyConnected = [ usbDevice for usbDevice in currentlyConnectedDevices if usbDevice not in self.usbDevices]
        self.usbDevices = currentlyConnectedDevices

        print(newlyConnected)
        return newlyConnected

    def newlyDisconnectedUSBDevices(self):
        currentlyConnectedDevices = connectedUSBDevices()
        newlyDisconnected = [ usbDevice for usbDevice in self.usbDevices if usbDevice not in currentlyConnectedDevices]
        self.usbDevices = currentlyConnectedDevices

        return newlyDisconnected

    def matchUSBDeviceWithPhysicalDevice(self, usbDevice):
        return DebugPhysicalDevice()

    @property
    def isMonitoring(self):
        with self.lock:
            return self.monitoring is not None
    
    def stopMonitoring(self):
        if self.isMonitoring:
            NotificationCenter().postNotification(DeviceManagerNotification.willStopMonitoring, notifyingObject=self)
            with self.lock:
                self.quitMonitoring = True
            self.monitoring.join()
            self.monitoring = None
        else:
            raise RuntimeError("No monitoring loop running")

    def addDevice(self, device):
        NotificationCenter().postNotification(DeviceManagerNotification.willAddDevice, notifyingObject=self, userInfo=device)
        with self.lock:
            self.devices.add(device)
        NotificationCenter().postNotification(DeviceManagerNotification.didAddDevice, notifyingObject=self, userInfo=device)

    def removeDevice(self, device):
        NotificationCenter().postNotification(DeviceManagerNotification.willRemoveDevice, notifyingObject=self, userInfo=device)
        with self.lock:
            self.devices.remove(device)
        NotificationCenter().postNotification(DeviceManagerNotification.didRemoveDevice, notifyingObject=self, userInfo=device)

    def matchPhysicalDevicesOfType(self, deviceClass, serialNumber=None):
        with self.lock:
            matched = []
            for device in self.devices:
                if issubclass(type(device), deviceClass):
                    if serialNumber is not None:
                        regexSerialNumber = serialNumber
                        regMatch = re.match(regexSerialNumber, device.serialNumber)
                        if regMatch is not None:
                            matched.append(device)
                    else:
                        matched.append(device)
            return matched

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
        expectedMaxEndTime = startTime + 0.7
        time.sleep(0.5)
        dm.stopMonitoring()
        self.assertTrue(expectedMaxEndTime > time.time() )

    def testRestartRunLoop(self):
        dm = DeviceManager()

        startTime = time.time()
        expectedMaxEndTime = startTime + 0.3
        dm.startMonitoring()
        dm.stopMonitoring()
        self.assertTrue(expectedMaxEndTime > time.time() )

        startTime = time.time()
        expectedMaxEndTime = startTime + 0.3
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
        nc.addObserver(self, self.handle, DeviceManagerNotification.willAddDevice)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didAddDevice)
        nc.addObserver(self, self.handle, DeviceManagerNotification.willRemoveDevice)
        nc.addObserver(self, self.handle, DeviceManagerNotification.didRemoveDevice)

        self.notificationsToReceive = [DeviceManagerNotification.willAddDevice,DeviceManagerNotification.didAddDevice]*1000
        self.notificationsToReceive.extend([DeviceManagerNotification.willRemoveDevice,DeviceManagerNotification.didRemoveDevice]*1000)


        dm.startMonitoring()
        time.sleep(0.5)
        self.addRemoveManyDevices(1000)
        time.sleep(0.5)
        dm.stopMonitoring()

        with self.lock:
            self.assertTrue(len(self.notificationsToReceive) == 0)        
        nc.removeObserver(self)

    def testNewlyConnectedDevices(self):
        dm = DeviceManager()
        self.assertTrue(len(dm.newlyConnectedUSBDevices()) > 4)


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
