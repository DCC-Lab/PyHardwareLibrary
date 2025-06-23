import env
import unittest

from serial.tools.list_ports import comports

from hardwarelibrary.communication.serialport import SerialPort


class TestSerialModule(unittest.TestCase):
    def setUp(self):
        raise(unittest.SkipTest("Uncomment this to run tests with FTDI devices connected. Skipping."))

    @unittest.skip
    def testListPorts(self):
        for c in comports():
            if c.vid is not None and c.pid is not None:
                print("0x{0:04x} 0x{1:04x} {2}".format(c.vid, c.pid, c.device))
            # print(c.serial_number)
            
    def testMatchPort(self):
        ports = SerialPort.matchPorts(idVendor=0x0403)
        self.assertTrue(len(ports) != 0)
        self.assertTrue(len(ports) == 1)

    def testMatchUniquePort(self):
        port = SerialPort.matchSinglePort(idVendor=0x0403)
        self.assertIsNotNone(port)

    def testMatchVendor(self):
        self.assertIsNotNone(SerialPort(idVendor=0x0403))
        self.assertIsNotNone(SerialPort(idVendor=0x0403, idProduct=0x6001))
        self.assertIsNotNone(SerialPort(idVendor=0x0403, idProduct=0x6001, serialNumber="ftDXIKC4"))

    def testMatchVendorProduct(self):
        self.assertIsNotNone(SerialPort(idVendor=0x0403, idProduct=0x6001))

    def testMatchVendorProductSerial(self):
        self.assertIsNotNone(SerialPort(idVendor=0x0403, idProduct=0x6001, serialNumber="ftDXIKC4"))

if __name__ == '__main__':
    unittest.main()
