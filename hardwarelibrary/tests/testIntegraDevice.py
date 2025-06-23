import env
import unittest
import time
import unittest

from hardwarelibrary.communication import USBPort, TextCommand, MultilineTextCommand
from hardwarelibrary.powermeters import *


class TestIntegraDevice(unittest.TestCase):
    device = None
    def setUp(self):
        self.device = IntegraDevice()
        self.assertIsNotNone(self.device)
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()

    def testDeviceVersion(self):
        self.device.doGetVersion()
        self.assertTrue(self.device.version == 'Integra Version 2.00.08')

    def testPower(self):
        self.assertTrue(self.device.measureAbsolutePower() > -0.5)
        print(self.device.measureAbsolutePower())

    def testCalibration(self):
        self.assertTrue(self.device.getCalibrationWavelength() > 100)
        print(self.device.getCalibrationWavelength())

    def testSetCalibration(self):
        self.device.setCalibrationWavelength(900)
        self.assertEqual(self.device.getCalibrationWavelength(), 900)

class TestIntegraPort(unittest.TestCase):
    port = None
    def setUp(self):
        self.port = USBPort(idVendor=0x1ad5, idProduct=0x0300, interfaceNumber=0, defaultEndPoints=(1,2))
        try:
            self.port.open()
        except:
            raise (unittest.SkipTest("No devices connected"))

    def tearDown(self):
        self.port.close()


    def testCreate(self):
        self.assertIsNotNone(self.port)

    def testReadPower(self):
        self.port.writeData(data=b"*CVU\r")
        reply = self.port.readString()
        self.assertIsNotNone(reply)
        self.assertTrue(float(reply) != 0)

    def testValidateCommands(self):
        commands = [b'*VEr',b'*STS', b'ST2', b'*CVU',b'*GWL',b'*GAN',b'*GZO',b'*GAS',b'*GCR',b'SSU',b'SSD',b'*DVS']
        for command in commands:
            self.port.writeData(data=command)
            try:
                if command != b'*DVS':
                    reply = self.port.readString()
                    self.assertIsNotNone(reply)
                else:
                    while True:
                        try:
                            reply = self.port.readString()
                            self.assertIsNotNone(reply)
                        except:
                            break
            except:
                print("Nothing returned for command {0}".format(command))

    def testTextCommandsNoParameter(self):
        commands = [
         TextCommand(name="GETPOWER", text="*CVU", replyPattern = r"(.+?)\r\n"),
         TextCommand(name="VERSION", text="*VER", replyPattern = r"(.+?)\r\n"),
         MultilineTextCommand(name="STATUS", text="*STS", replyPattern = r"(.+?)\r\n", lastLinePattern=":100000000"),
         TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+?)\r\n")
        ]

        for command in commands:
            self.assertFalse(command.send(port=self.port),msg=command.exceptions)
            with self.assertRaises(Exception):
                leftover = self.port.readString()
                print("Characters left after command {1}: {0}".format(leftover, command.name))


    def testStatusCommand(self):
        #TextCommand(name="STATUS", text="*STS", replyPattern=r"(.+)\r\n", finalReplyPattern=":100000000"),
        self.port.writeString("*STS")

        for i in range(47):
            try:
                reply = self.port.readString()
            except:
                print("Failed at i {0}".format(i))

    def testIntegraBugUnresponsiveAfterSetWavelength(self):
        """ While testing an Integra new version with a UP19K-15S-H5-INT-D0, 
        I found that the setwavelength command requires
        a sleep after being sent (it does not confirm the command with anything).
        If we don't sleep, the next command will return nothing.
        My experience is that the required delay can be as low as 0.023 and as high as 0.03

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
        """ See above.
        """
        setCommand = TextCommand(name="SETWAVELENGTH", text="*PWC{0:05d}")
        getCommand = TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+?)\r\n")

        self.port.defaultTimeout = 2000
        setCommand.send(port=self.port, params=(800))
        # We except an error! setting a long timeout is not enough
        self.assertTrue(getCommand.send(port=self.port))
        self.assertTrue(isinstance(getCommand.exceptions[0], OSError))

    def testIntegraBugUnresponsiveOnlyAfterSetWavelength(self):
        """ See above.
        """
        setCommand = TextCommand(name="SETAUTOSCALE", text="*SAS1")
        getCommand = TextCommand(name="GETWAVELENGTH", text="*GWL", replyPattern = r"PWC\s*:\s*(.+?)\r\n")
        # This will succeed, so it's only Setwavelength that is the problem
        setCommand.send(port=self.port, params=(800))
        time.sleep(0.001)
        self.assertFalse(getCommand.send(port=self.port),msg="Surprisingly succeeded sending command with delay 0.001")

if __name__ == '__main__':
    unittest.main()
