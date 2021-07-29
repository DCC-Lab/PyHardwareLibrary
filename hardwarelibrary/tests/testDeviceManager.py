import env # modifies path
import unittest
import time
from threading import Thread, Lock
import numpy as np
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.motion import DebugLinearMotionDevice, LinearMotionDevice
from hardwarelibrary.motion import SutterDevice


class DeviceManager:
    _instance = None
    def __init__(self):
        if not hasattr(self, 'devices'):
            self.devices = []

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance

    def addDevice(self, device):
    	self.devices.append(device)

    def matchPhysicalDevicesOfType(self, deviceClass):
    	matched = []
    	for device in self.devices:
    		if issubclass(type(device), deviceClass):
    			matched.append(device)
    	return matched


class TestDeviceManager(unittest.TestCase):

    def testIsRunning(self):
        self.assertTrue(True)

    def testInstanciate(self):
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
        # self.assertTrue( issubclass( type(device), LinearMotionDevice ))

    def testMatching(self):
        dm = DeviceManager()
        device = DebugLinearMotionDevice()
        dm.addDevice(device)

        matched = dm.matchPhysicalDevicesOfType(DebugLinearMotionDevice)
        self.assertTrue(len(matched) > 0)




if __name__ == '__main__':
	unittest.main()
