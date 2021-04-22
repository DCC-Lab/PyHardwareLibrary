import env # modifies path
import unittest
import time
from threading import Thread, Lock

from serial import *
from hardwarelibrary.communication import USBPort, TextCommand
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
        self.assertTrue(float(reply) != 0)

    # def testReadPowerForever(self):
    #     while True:
    #         self.port.writeData(data=b"*CVU")
    #         reply = self.port.readString()
    #         self.assertIsNotNone(reply)
    #         print("Power is {0:0.1f}".format(float(reply)*1000))

    def testValidateCommands(self):
        commands = [b'*VEr',b'*STS', b'ST2', b'*CVU',b'*GWL',b'*GAN',b'*GZO',b'*GAS',b'*GCR',b'SSU',b'SSD',b'*DVS']
        for command in commands:
            self.port.writeData(data=command)
            try:
                if command != b'*DVS':
                    reply = self.port.readString()
                    self.assertIsNotNone(reply)
                    # print("{0} replied {1}".format(command, reply))
                else:
                    while True:
                        try:
                            reply = self.port.readString()
                            self.assertIsNotNone(reply)
                            # print("{0} replied {1}".format(command, reply))
                        except:
                            break
            except:
                print("Nothing returned for command {0}".format(command))

    def testTryCommand(self):
        getPower = TextCommand(name="GETPOWER", text="*CVU", replyPattern = r"(.+)\r\n")
        self.assertFalse(getPower.send(port=self.port),getPower.exceptions)
        print(getPower.matchAsFloat)

if __name__ == '__main__':
    unittest.main()
