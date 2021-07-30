import env # modifies path
import unittest
import numpy as np
import time
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.motion import DebugLinearMotionDevice, LinearMotionDevice
from hardwarelibrary.motion import SutterDevice
import re
from multiprocessing import Process, Value, Array
from threading import Thread, Lock

class DeviceManager:
    _instance = None

    def __init__(self):
        if not hasattr(self, 'devices'):
            self.devices = set()
        if not hasattr(self, 'quitMonitoring'):
            self.quitMonitoring = False
        if not hasattr(self, 'lock'):
            self.lock = Lock()
        if not hasattr(self, 'monitoring'):
            self.monitoring = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def startMonitoring(self):
        with self.lock:
            if self.monitoring is None:
                self.monitoring = Thread(target=self.monitoringLoop, name="DeviceManager-RunLoop")
                self.quitMonitoring = False
                self.monitoring.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    def monitoringLoop(self):        
        startTime = time.time()
        endTime = startTime + 5.0
        while time.time() < endTime :
            time.sleep(0.3)
            with self.lock:
                if self.quitMonitoring:
                     break

    def stopMonitoring(self):
        with self.lock:
            if self.monitoring is not None:
                self.quitMonitoring = True
            else:
                raise RuntimeError("No monitoring loop running")
                
        self.monitoring.join()

    def addDevice(self, device):
        with self.lock:
            self.devices.add(device)

    def matchPhysicalDevicesOfType(self, deviceClass, serialNumber=None):
        currentDevices = []
        with self.lock:
            currentDevices.extend(self.devices)

        matched = []
        for device in currentDevices:
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

    def testMatchingWithSerial(self):
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
        expectedMaxEndTime = startTime + 1.5
        time.sleep(1)
        dm.stopMonitoring()
        self.assertTrue(expectedMaxEndTime > time.time() )

if __name__ == '__main__':
    unittest.main()
