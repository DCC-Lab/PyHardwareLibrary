import env
import unittest
from threading import Thread, Lock

import usb.util as util

from hardwarelibrary.communication import *

payloadData = b'1234'
payloadString = '1234\n'
globalLock = Lock()
threadFailed = -1


class BaseTestCases:
    class TestEchoPort(unittest.TestCase):
        port = None

        def testCreate(self):
            self.assertIsNotNone(self.port)

        def testIsOpenOnCreation(self):
            self.assertTrue(self.port.isOpen)

        def testCantReopen(self):
            self.assertTrue(self.port.isOpen)
            with self.assertRaises(Exception):
                self.port.open()

        def testCloseReopen(self):
            self.assertTrue(self.port.isOpen)
            self.port.close()
            self.port.open()

        def testCloseTwice(self):
            self.assertTrue(self.port.isOpen)
            self.port.close()
            self.port.close()

        def testWriteData(self):
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))

        def testWriteDataBytesAvailable(self):
            nBytes = self.port.writeData(payloadData)
            self.assertEqual(nBytes, len(payloadData))
            # We are testing an echo, there may be a delay.
            time.sleep(0.1)
            self.assertEqual(nBytes, self.port.bytesAvailable())

        def testWriteDataReadEcho(self):
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))

            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData, "Data {0}, payload:{1}".format(data, payloadData))

        def testWriteDataReadEchoSequence(self):
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))

            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData, "Data {0}, payload:{1}".format(data, payloadData))
            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData, "Data {0}, payload:{1}".format(data, payloadData))

        def testWriteDataReadEchoLarge(self):
            for i in range(100):
                nBytes = self.port.writeData(payloadData)
                self.assertTrue(nBytes == len(payloadData))

            for i in range(100):
                data = self.port.readData(length=len(payloadData))
                self.assertTrue(data == payloadData, "Data {0}, payload:{1}".format(data, payloadData))

        # def testWriteString(self):
        #     nBytes = self.port.writeString(payloadString)
        #     self.assertTrue(nBytes == len(payloadString))

        def testWriteStringReadEcho(self):
            nBytes = self.port.writeString(payloadString)
            self.assertTrue(nBytes == len(payloadString))

            string = self.port.readString()
            self.assertTrue(string == payloadString, "String {0}, payload:{1}".format(string, payloadString))

        def testWriteStringReadEchoSequence(self):
            nBytes = self.port.writeString(payloadString)
            self.assertTrue(nBytes == len(payloadString))
            nBytes = self.port.writeString(payloadString)
            self.assertTrue(nBytes == len(payloadString))

            string = self.port.readString()
            self.assertTrue(string == payloadString)
            string = self.port.readString()
            self.assertTrue(string == payloadString)

        def testWriteStringReadEchoLarge(self):
            for i in range(100):
                nBytes = self.port.writeString(payloadString)
                self.assertTrue(nBytes == len(payloadString))

            for i in range(100):
                string = self.port.readString()
                self.assertTrue(string == payloadString, "{0} is not {1}".format(string, payloadString))

        def testTimeoutReadData(self):
            with self.assertRaises(CommunicationReadTimeout):
                self.port.readData(1)

            self.port.writeData(payloadData)
            with self.assertRaises(CommunicationReadTimeout):
                self.port.readData(len(payloadData) + 1)

        def testWriteStringReadMatchingEcho(self):
            reply = self.port.writeStringExpectMatchingString(
                payloadString,
                replyPattern=payloadString)
            self.assertEqual(reply, payloadString)

        def testWriteStringReadMatchingPattern(self):
            reply = self.port.writeStringExpectMatchingString(
                "abcd1234\n",
                replyPattern="abc.\\d{4}")
            self.assertEqual(reply, "abcd1234\n")

        def testWriteStringReadMatchingPatternFirstCaptureGroup(self):
            reply, firstGroup = self.port.writeStringReadFirstMatchingGroup(
                "abcd1234\n",
                replyPattern="abc.(\\d{4})")
            self.assertEqual(firstGroup, "1234")

        def testWriteStringReadMatchingPatternAllCaptureGroups(self):
            reply, groups = self.port.writeStringReadMatchingGroups(
                "abcd1234\n",
                replyPattern="(abc.)(\\d{4})")
            self.assertEqual(groups[0], "abcd")
            self.assertEqual(groups[1], "1234")

        def testFailedWriteStringReadMatchingPattern(self):
            with self.assertRaises(CommunicationReadNoMatch):
                _ = self.port.writeStringExpectMatchingString(
                    "abcd1234\n",
                    replyPattern="abc.\\d{5}")

        def testFailedWriteStringReadMatchingPatternFirstCaptureGroup(self):
            with self.assertRaises(CommunicationReadNoMatch):
                _ = self.port.writeStringReadFirstMatchingGroup(
                    "abcd1234\n",
                    replyPattern="abc.(\\d{5})")

        def testFailedWriteStringReadMatchingPatternWithoutGroupFirstCaptureGroup(self):
            with self.assertRaises(CommunicationReadNoMatch):
                _ = self.port.writeStringReadFirstMatchingGroup(
                    "abcd1234\n",
                    replyPattern="abc.\\d{4}")

        def testFailedWriteStringReadMatchingPatternAllCaptureGroups(self):
            with self.assertRaises(CommunicationReadNoMatch):
                (_, _) = self.port.writeStringReadMatchingGroups(
                    "abcd1234\n",
                    replyPattern="(abc.)(\\d{5})")

        def testThreadSafety(self):
            global threadFailed, globalLock
            threadFailed = -1
            threadPool = []
            for i in range(100):
                process = Thread(target=threadReadWrite, kwargs=dict(port=self.port, index=i))
                threadPool.append(process)

            for process in threadPool:
                process.start()

            for i, p in enumerate(threadPool):
                p.join(timeout=1)

                with globalLock:
                    if threadFailed != -1:
                        self.fail("Thread {0}?".format(threadFailed))

            for i, p in enumerate(threadPool):
                p.join(timeout=1)

            with globalLock:
                if threadFailed != -1:
                    self.fail("Thread {0}?".format(threadFailed))

        def testTextCommandNoReply(self):
            command = TextCommand("Test", text="1234\n")
            self.assertIsNotNone(command)
            self.assertFalse(command.send(self.port))
            self.assertTrue(command.isSentSuccessfully)
            self.assertIsNone(command.reply)
            self.assertFalse(command.hasError)

        def testTextCommand(self):
            command = TextCommand("Test", text="1234\n", replyPattern="1234")
            self.assertIsNotNone(command)
            self.assertFalse(command.send(self.port))
            self.assertTrue(command.isSentSuccessfully)
            self.assertTrue(command.reply == "1234\n")
            self.assertFalse(command.hasError)

        def testDataCommandNoReply(self):
            command = DataCommand("Test", data=b"1234\n")
            self.assertIsNotNone(command)
            self.assertFalse(command.send(self.port))
            self.assertTrue(command.isSentSuccessfully)
            self.assertIsNone(command.reply)
            self.assertFalse(command.hasError)

        def testDataCommand(self):
            command = DataCommand("Test", data=b"1234\n", replyDataLength=5)
            self.assertIsNotNone(command)
            self.assertFalse(command.send(self.port), msg="Exceptions were {0}".format(command.exceptions))
            self.assertTrue(command.isSentSuccessfully)
            self.assertTrue(command.reply == b"1234\n", msg="Reply was: {0}".format(command.reply))
            self.assertFalse(command.hasError)

        def testDataCommandError(self):
            command = DataCommand("Test", data=b"1234\n", replyDataLength=6)
            self.assertIsNotNone(command)
            with self.assertRaises(Exception):
                command.send(self.port)
            self.assertFalse(command.isSentSuccessfully)
            self.assertTrue(command.hasError)


def threadReadWrite(port, index):
    global threadFailed, globalLock
    payload = "abcd{0}\n".format(index)
    with globalLock:
        try:
            port.writeStringExpectMatchingString(payload, replyPattern=payload)
        except Exception:
            if threadFailed != -1:
                threadFailed = index


class TestDebugEchoPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        self.port = DebugEchoPort()
        self.assertIsNotNone(self.port)
        self.port.open()
        self.assertTrue(self.port.isOpen)
        self.port.flush()

    def tearDown(self):
        self.port.close()
        self.assertFalse(self.port.isOpen)


class TestDebugPortDefaultsToECho(BaseTestCases.TestEchoPort):

    def setUp(self):
        self.port = DebugPort()
        self.assertIsNotNone(self.port)
        self.port.open()
        self.assertTrue(self.port.isOpen)
        self.port.flush()

    def tearDown(self):
        self.port.close()
        self.assertFalse(self.port.isOpen)


class TestFTDIAdaptor(unittest.TestCase):

    # def testFindDevice(self):
    #     dev = usb.core.find(idVendor=0x0403, idProduct=0x6001)
    #     self.assertIsNotNone(dev)

    # def testFindConfigureDevice(self):
    #     dev = usb.core.find(idVendor=0x0403, idProduct=0x6001)
    #     self.assertIsNotNone(dev)
    #     dev.set_configuration()
    #     cfg = dev.get_active_configuration()
    #     self.assertIsNotNone(cfg)

    # def testFindConfigureInterfaceDevice(self):
    #     dev = usb.core.find(idVendor=0x0403, idProduct=0x6001)
    #     self.assertIsNotNone(dev)
    #     dev.set_configuration()
    #     cfg = dev.get_active_configuration()
    #     self.assertIsNotNone(cfg)
    #     itf = cfg[(0,0)]

    @unittest.skip("It is not possible to write directly to endpoints of FTDI chip")
    def testFindConfigureInterfaceEndpointsDevice(self):
        dev = usb.core.find(idVendor=0x0403, idProduct=0x6001)
        dev.set_configuration()
        cfg = dev.get_active_configuration()
        self.assertIsNotNone(cfg)
        itf = cfg[(0, 0)]
        epIn = itf[0]
        epOut = itf[1]
        self.assertTrue(epIn.bEndpointAddress & 0x80 != 0)
        self.assertTrue(epOut.bEndpointAddress & 0x80 == 0)

        # We cannot do this: writing to endpoints is not the way to use the device
        # There seems to be a bit more information that is sent into these endpoints
        maxPacket = epIn.wMaxPacketSize
        data = util.create_buffer(maxPacket)
        nBytes = epIn.read(size_or_buffer=data, timeout=1000)
        print(nBytes, data)

        text = b'aaaabbbbccccddddeeeeffff'
        epOut.write(text)
        epOut.write(text)
        epOut.write(text)
        data = util.create_buffer(maxPacket)
        nBytes = epIn.read(size_or_buffer=data, timeout=1000)
        print(nBytes, data[:nBytes])
        for c in data[:nBytes]:
            print("{0:08b} ".format(c), end='')


class TestSlowDebugEchoPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        self.port = DebugEchoPort()
        self.assertIsNotNone(self.port)
        self.port.open()
        self.assertTrue(self.port.isOpen)
        self.port.delay = 0.01
        self.port.flush()

    def tearDown(self):
        self.port.close()


class TestRealEchoSerialPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        try:
            self.port = SerialPort(idVendor=0x0403, idProduct=0x6001, serialNumber="FTDXIKC4")
            self.assertIsNotNone(self.port)
            self.port.open()
            self.port.flush()
        except Exception as err:
            raise (unittest.SkipTest("No ECHO device connected {0}".format(err)))

    def tearDown(self):
        if self.port is not None:
            self.port.flush()
            self.port.close()


if __name__ == '__main__':
    unittest.main()
