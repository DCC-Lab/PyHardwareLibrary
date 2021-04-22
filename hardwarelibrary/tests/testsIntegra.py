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
        commands = [
         TextCommand(name="GETPOWER", text="*CVU", replyPattern = r"(.+)\r\n"),
         TextCommand(name="VERSION", text="*VER", replyPattern = r"(.+)\r\n"),
         TextCommand(name="STATUS", text="*STS", replyPattern = r"(.+)\r\n")
        ]

        for command in commands:
            self.assertFalse(command.send(port=self.port),command.exceptions)
            print(command.matchGroups[0])

    def testCommandWithParameter(self):
        command = TextCommand(name="SETWAVELENGTH", text="*PWC{0:05d}", replyPattern = None)
        self.assertFalse(command.send(port=self.port,params=(800)),command.exceptions)
        command = TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+)\r\n")
        self.assertFalse(command.send(port=self.port),command.exceptions)
        self.assertTrue(command.matchAsFloat(0) == 800)

if __name__ == '__main__':
    unittest.main()
