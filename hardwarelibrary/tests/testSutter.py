import env # modifies path
import unittest
import time
from threading import Thread, Lock
from struct import *

from hardwarelibrary.motion.sutterdevice import SutterDevice, SutterDebugSerialPort 
from hardwarelibrary.communication.serialport import SerialPort

class TestSutterSerialPortBase(unittest.TestCase):
    port = None

    def setUp(self):
        self.port = SerialPort(idVendor=0x1342, idProduct=0x0001)
        self.port.open()

    def tearDown(self):
        self.port.close()

    def testCreate(self):
        self.assertIsNotNone(self.port)

    def testCantReopen(self):
        self.assertIsNotNone(self.port)
        self.assertTrue(self.port.isOpen)
        with self.assertRaises(Exception) as context:
            self.port.open()

    def testCloseReopen(self):
        self.assertIsNotNone(self.port)
        self.assertTrue(self.port.isOpen)
        self.port.close()
        self.port.open()

    def testCloseTwice(self):
        self.assertIsNotNone(self.port)
        self.assertTrue(self.port.isOpen)
        self.port.close()
        self.port.close()

    def testCantReadEmptyPort(self):
        self.assertIsNotNone(self.port)
        self.assertTrue(self.port.isOpen)
        with self.assertRaises(CommunicationReadTimeout) as context:
            self.port.readString()

    def testMove(self):
        self.assertIsNotNone(self.port)
        payload = bytearray('m',encoding='utf-8')
        payload.extend(pack("<lll",1,2,3))
        self.port.writeData(payload)
        self.assertTrue(self.port.readData(length=1) == b'\r')

    def testMoveGet(self):
        self.assertIsNotNone(self.port)
        payload = bytearray('m',encoding='utf-8')
        payload.extend(pack("<lll",1,2,3))
        self.port.writeData(payload)
        self.assertTrue(self.port.readData(length=1) == b'\r')

        payload = bytearray('c',encoding='utf-8')
        self.port.writeData(payload)
        data = self.port.readData(length=4*3)
        (x,y,z) = unpack("<lll", data)
        self.assertTrue( x == 1)
        self.assertTrue( y == 2)
        self.assertTrue( z == 3)


class TestSutterDevice(unittest.TestCase):
    def setUp(self):
        self.device = SutterDevice()
        self.assertIsNotNone(self.device)

    def testDevicePosition(self):
        (x,y,z) = self.device.positionInMicrosteps()
        self.assertTrue(x>0)
        self.assertTrue(y>0)
        self.assertTrue(z>0)
    def testDeviceMove(self):
        self.device.moveTo(1,2,3)

        (x,y,z) = self.device.position()
        self.assertTrue(x==1)
        self.assertTrue(y==2)
        self.assertTrue(z==3)

    def testDeviceMoveBy(self):
        (xo,yo,zo) = self.device.position()

        self.device.moveBy(10,20,30)

        (x,y,z) = self.device.position()
        self.assertTrue(x-x0 == 10)
        self.assertTrue(y-y0 == 20)
        self.assertTrue(z-z0 == 30)

if __name__ == '__main__':
    unittest.main()
