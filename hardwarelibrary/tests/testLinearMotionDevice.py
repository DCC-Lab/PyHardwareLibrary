import env # modifies path
import unittest
import time
import os
from struct import *

from hardwarelibrary.communication import *
from hardwarelibrary.motion.linearmotiondevice import DebugLinearMotionDevice
from hardwarelibrary.motion.sutterdevice import SutterDevice

import serial

class TestLinearMotionDevice(unittest.TestCase):
    def setUp(self):
        self.device = DebugLinearMotionDevice()

    # def testDeviceHome(self):
    #     self.device.home()

    def testDevicePosition(self):
        (x, y, z) = self.device.position()
        self.assertIsNotNone(x)
        self.assertIsNotNone(y)
        self.assertIsNotNone(z)
        self.assertTrue(x >= 0)
        self.assertTrue(y >= 0)
        self.assertTrue(z >= 0)

    def testPosition(self):
        (x, y, z) = self.device.position()
        self.assertIsNotNone(x)
        self.assertIsNotNone(y)
        self.assertIsNotNone(z)
        self.assertTrue(x >= 0)
        self.assertTrue(y >= 0)
        self.assertTrue(z >= 0)

    def testDeviceMove(self):
        destination = (4000, 5000, 6000)
        self.device.moveTo(destination)

        (x,y,z) = self.device.position()
        self.assertTrue(x == destination[0])
        self.assertTrue(y == destination[1])
        self.assertTrue(z == destination[2])

    def testDeviceMoveBy(self):
        (xo, yo, zo) = self.device.position()

        self.device.moveBy((-1000, -2000, -3000))

        (x, y, z) = self.device.position()
        self.assertTrue(x-xo == -1000)
        self.assertTrue(y-yo == -2000)
        self.assertTrue(z-zo == -3000)




# class TestSutterIntegration(unittest.TestCase):
#     def setUp(self):
#         self.port = None
#         self.portPath = None

#         ports = serial.tools.list_ports.comports()
#         for port in ports:
#             if port.vid == 4930 and port.pid == 1: # Sutter Instruments
#                 self.portPath = port.device

#         if self.portPath is None:
#             self.fail("No Sutter connected. Giving up.")

#     def tearDown(self):
#         if self.port is not None:
#             self.port.close()

#     def move(self, x,y,z):
#         # Write this or copy/paste from above...
#         self.assertTrue(False)

#     def getPosition(self):
#         # Write this or copy/paste from above...
#         self.assertTrue(False)

#     def testMove(self):
#         self.assertTrue(False)

#     def testMoveAndConfirmPosition(self):
#         self.assertTrue(False)

#     def testMoveSeveralTimes(self):
#         self.assertTrue(False)

#     def testReadPosition(self):
#         self.assertTrue(False)

#     def testReadPositionSeveralTimes(self):
#         self.assertTrue(False)


if __name__ == '__main__':
    unittest.main()
