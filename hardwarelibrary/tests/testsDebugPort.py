import env # modifies path
import unittest

from hardwarelibrary.communication.usbport import USBPort

class TestSutterSerialPortBase(unittest.TestCase):
    port = None

    def setUp(self):
        self.port = USBPort(idVendor=0x1342, idProduct=0x0001)
        self.port.open()
        #self.port = DebugPort() 

    def tearDown(self):
        self.port.close()

    def testCreate(self):
        self.assertIsNotNone(self.port)


if __name__ == '__main__':
    unittest.main()
