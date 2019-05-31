import env # modifies path
import unittest
import time
from threading import Thread, Lock
from struct import *

from serial import *
from hardwarelibrary import *

class BaseTestCases:

    class TestSutterSerialPort(unittest.TestCase):
        port = None

        def testCreate(self):
            self.assertIsNotNone(self.port)

        def testCantReopen(self):
            self.assertTrue(self.port.isOpen)
            with self.assertRaises(Exception) as context:
                self.port.open()

        def testCloseReopen(self):
            self.assertTrue(self.port.isOpen)
            self.port.close()
            self.port.open()

        def testCloseTwice(self):
            self.assertTrue(self.port.isOpen)
            self.port.close()
            self.port.close()

        def testCantReadEmptyPort(self):
            self.assertTrue(self.port.isOpen)
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readString()

        def testMove(self):
            payload = bytearray('m',encoding='utf-8')
            payload.extend(pack("<lll",1,2,3))
            self.port.writeData(payload)
            self.assertTrue(self.port.readData(length=1) == b'\r')

        def testMoveGet(self):
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


class TestDebugSutterSerialPort(BaseTestCases.TestSutterSerialPort):

    def setUp(self):
        self.port = SutterDebugSerialPort()
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()


if __name__ == '__main__':
    unittest.main()
