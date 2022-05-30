import env
import os
import unittest
import struct
import time

from hardwarelibrary.communication.serialport import SerialPort

hardcodedPath = '/dev/cu.usbserial-ftDXIKC4'


class SerialHardwareControl(unittest.TestCase):
    idVendor = 0x0403
    idProduct = 0x6001

    port = None
    def setUp(self):
        if not os.path.exists(hardcodedPath):
            raise(unittest.SkipTest("No Tektronik scope connected. Skipping."))
        self.port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct)
        self.assertIsNotNone(self.port)
        self.port.open(baudRate=9600, timeout=3.0, rtscts=True, dsrdtr=None)
        self.assertTrue(self.port.isOpen)
        self.port.flush()


    def tearDown(self):
        if self.port is not None:
            self.port.close()
            self.port = None


    def testHardwareLinesDTR(self):
        self.port.port.dtr = False
        time.sleep(1)
        self.port.port.dtr = True
        time.sleep(1)
        self.port.port.dtr = False
        time.sleep(1)
        # stb, esr, errors = self.getStatus()
        # self.assertTrue(esr == 0)
        # for i in range(10):
        #     stb, esr, errors = self.getStatus()
        #     self.assertTrue(esr == 0)
        #     print(self.port.port.dtr, self.port.port.dsr, self.port.port.rts, self.port.port.cts)
    def testHardwareLinesRTS(self):
        self.port.port.rts = False
        time.sleep(1)
        self.port.port.rts = True
        time.sleep(1)
        self.port.port.rts = False
        time.sleep(1)

    def testCTS(self):
        while True:
            print("Unasserted!", self.port.port.cts, self.port.port.dtr)


if __name__ == '__main__':
    unittest.main()
