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

    def testTextCommandsNoParameter(self):
        commands = [
         TextCommand(name="GETPOWER", text="*CVU", replyPattern = r"(.+?)\r\n"),
         TextCommand(name="VERSION", text="*VER", replyPattern = r"(.+?)\r\n"),
         TextCommand(name="STATUS", text="*STS", replyPattern = r"(.+?)\r\n", finalReplyPattern=":100000000"),
         TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+?)\r\n")
        ]

        for command in commands:
            self.assertFalse(command.send(port=self.port),command.exceptions)
            print(command.matchGroups[0])

            with self.assertRaises(Exception):
                leftover = self.port.readString()
                print("Characters left after command {1}: {0}".format(leftover, command.name))


    def testStatusCommand(self):
        TextCommand(name="STATUS", text="*STS", replyPattern=r"(.+)\r\n", finalReplyPattern=":100000000"),

        self.port.writeString("*STS")
        try:
            while True:
                reply = self.port.readString()
                if reply == ':100000000':
                    break
        except:
            print("Done")

    def testIntegraBugUnresponsiveAfterSetWavelength(self):
        """ While testing, I found that the setwavelength command requires
        a sleep after (it does not confirm the command with anything).
        If we don't sleep, the GETWAVELENGTH will return nothing.
        My experience is that the delay can be as low as 0.023 and as high as 0.03

        It should always succeed for >0.05 and should always fail with ≤ 0.02
        It is not sufficient to set a longer timeout as demonstrated with
        testIntegraBugUnresponsiveAfterSetWavelengthMustSleep()
        """
        setCommand = TextCommand(name="SETWAVELENGTH", text="*PWC{0:05d}")
        getCommand = TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+?)\r\n")

        # This should succeed
        setCommand.send(port=self.port, params=(800))
        time.sleep(0.05)
        self.assertFalse(getCommand.send(port=self.port),msg="Surprinsingly failed sending command with delay 0.050 :{0}".format(getCommand.exceptions))
        self.assertAlmostEqual(getCommand.matchAsFloat(0), 800.0)

        # This should fail
        setCommand.send(port=self.port, params=(800))
        time.sleep(0.001)
        self.assertTrue(getCommand.send(port=self.port),msg="Surprisingly succeeded sending command with delay 0.001")

    def testIntegraBugUnresponsiveAfterSetWavelengthMustSleep(self):
        """ While testing, I found that the setwavelength command requires
        a sleep after (it does not confirm the command with anything).
        If we don't sleep, the GETWAVELENGTH will return nothing.
        My experience is that the delay can be as low as 0.023 and as high as 0.03

        It is not sufficient to set a longer timeout, as is demonstrated here
        """
        setCommand = TextCommand(name="SETWAVELENGTH", text="*PWC{0:05d}")
        getCommand = TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+?)\r\n")

        self.port.defaultTimeout = 2000
        setCommand.send(port=self.port, params=(800))
        # We except an error! setting a long timeout is not enough
        self.assertTrue(getCommand.send(port=self.port))
        self.assertTrue(isinstance(getCommand.exceptions[0], OSError))

if __name__ == '__main__':
    unittest.main()
