import env # modifies path
import unittest
import time
from threading import Thread, Lock

from serial import *
from hardwarelibrary.communication import USBPort 
import usb.core

class TestIntegraPort(unittest.TestCase):
    port = None
    def setUp(self):
        self.port = USBPort(idVendor=0x1ad5, idProduct=0x0300, interfaceNumber=0, defaultEndPoints=(1,2))

    def tearDown(self):
        self.port.close()

    def testCreate(self):
        self.assertIsNotNone(self.port)

    def testReadPower(self):
        self.port.writeData(data=b"*CVU\r")
        reply = self.port.readString()
        self.assertIsNotNone(reply)
        print("Power is {0}".format(reply))

    # def testReadPowerForever(self):
    #     while True:
    #         self.port.writeData(data=b"*CVU")
    #         reply = self.port.readString()
    #         self.assertIsNotNone(reply)
    #         print("Power is {0:0.1f}".format(float(reply)*1000))

    def testValidateCommands(self):
        commands = [b'*CVU',b'*GWL',b'*GAN',b'*GZO']
        for command in commands:
            self.port.writeData(data=command)
            reply = self.port.readString()
            self.assertIsNotNone(reply)


if __name__ == '__main__':
    unittest.main()
