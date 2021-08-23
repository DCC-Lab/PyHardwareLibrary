import env # modifies path
import unittest
import time
from threading import Thread, Lock
from physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.motion import DebugLinearMotionDevice
from hardwarelibrary.motion import SutterDevice

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

class BaseTestCases:
    class TestPhysicalDeviceBase(unittest.TestCase):
        def setUp(self):
            self.device = None
            self.isRunning = False

        def testIsRunning(self):
            self.assertFalse(self.isRunning)

        def testBaseInit(self):
            self.assertTrue(len(self.device.serialNumber) > 0)
            self.assertTrue(self.device.vendorId != 0)
            self.assertTrue(self.device.productId != 0)

        def testInitialUnconfiguredState(self):
            self.assertTrue(self.device.state == DeviceState.Unconfigured)

        def testConfiguredStateAfterInitialize(self):
            self.assertEqual(self.device.state, DeviceState.Unconfigured)
            self.device.initializeDevice()
            self.assertEqual(self.device.state, DeviceState.Ready)

        def testConfiguredStateSequenceToShutdown(self):        
            try:
                self.assertTrue(self.device.state == DeviceState.Unconfigured)
                self.device.initializeDevice()
                self.assertTrue(self.device.state == DeviceState.Ready)
                self.device.shutdownDevice()
                self.assertTrue(self.device.state == DeviceState.Recognized)
            except Exception as error:
                self.device.shutdownDevice()
                self.assertTrue(self.device.state == DeviceState.Unrecognized)


class TestDebugPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        self.device = DebugPhysicalDevice()

    def testConfiguredStateSequenceToShutdownWithInitError(self):
        self.device.errorInitialize = True
        self.assertTrue(self.device.state == DeviceState.Unconfigured)
        with self.assertRaises(Exception):
            self.device.initializeDevice()
        self.assertTrue(self.device.state == DeviceState.Unrecognized)
        self.device.shutdownDevice()
        self.assertTrue(self.device.state == DeviceState.Unrecognized)

    def testConfiguredStateSequenceToShutdownWithShutError(self):
        self.device.errorShutdown = True
        self.assertTrue(self.device.state == DeviceState.Unconfigured)
        self.device.initializeDevice()
        self.assertTrue(self.device.state == DeviceState.Ready)
        with self.assertRaises(Exception):
            self.device.shutdownDevice()
        self.assertTrue(self.device.state == DeviceState.Recognized)

class TestLinearMotionPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        self.device = DebugLinearMotionDevice()

class TestSutterPhysicalDevice(BaseTestCases.TestPhysicalDeviceBase):
    def setUp(self):
        super().setUp()
        self.device = SutterDevice(serialNumber="debug")


if __name__ == '__main__':
    unittest.main()
