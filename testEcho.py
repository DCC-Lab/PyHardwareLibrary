import unittest
from serial import *
from SerialPort import *
import time
from threading import Thread, Lock

payloadData = b'1234'
payloadString = '1234\n'
globalLock = Lock()
threadFailed = -1

class BaseTestCases:

    class TestEchoPort(unittest.TestCase):
        port = None

        def testCreate(self):
            self.assertIsNotNone(self.port)

        def testWriteData(self):
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))

        # def testWriteDataBytesAvailable(self):
        #     nBytes = self.port.writeData(payloadData)
        #     self.assertEqual(nBytes, self.port.bytesAvailable())

        def testWriteDataReadEcho(self):
            nBytes = self.port.writeData(payloadData)
            self.assertTrue(nBytes == len(payloadData))

            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData)

        def testWriteDataReadEchoSequence(self):
            nBytes = self.port.writeData(payloadData)
            nBytes = self.port.writeData(payloadData)

            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData)
            data = self.port.readData(length=len(payloadData))
            self.assertTrue(data == payloadData)

        def testWriteDataReadEchoLarge(self):
            for i in range(100):
                nBytes = self.port.writeData(payloadData)

            for i in range(100):
                data = self.port.readData(length=len(payloadData))
                self.assertTrue(data == payloadData)

        def testWriteString(self):
            nBytes = self.port.writeString(payloadString)
            self.assertTrue(nBytes == len(payloadString))

        def testWriteStringReadEcho(self):
            nBytes = self.port.writeString(payloadString)
            self.assertTrue(nBytes == len(payloadString))

            string = self.port.readString()
            self.assertTrue(string == payloadString, "String {0}, payload:{1}".format(string, payloadString))

        def testWriteStringReadEchoSequence(self):
            nBytes = self.port.writeString(payloadString)
            nBytes = self.port.writeString(payloadString)

            string = self.port.readString()
            self.assertTrue(string == payloadString)
            string = self.port.readString()
            self.assertTrue(string == payloadString)

        def testWriteStringReadEchoLarge(self):
            for i in range(100):
                nBytes = self.port.writeString(payloadString)

            for i in range(100):
                string = self.port.readString()
                self.assertTrue(string == payloadString)

        def testTimeoutReadData(self):
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readData(1)

            self.port.writeData(payloadData)
            with self.assertRaises(CommunicationReadTimeout) as context:
                self.port.readData(len(payloadData)+1)

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
            firstGroup = self.port.writeStringReadFirstMatchingGroup(
                        "abcd1234\n",
                        replyPattern="abc.(\\d{4})")
            self.assertEqual(firstGroup, "1234")

        def testWriteStringReadMatchingPatternAllCaptureGroups(self):
            (firstGroup, secondGroup) = self.port.writeStringReadMatchingGroups(
                        "abcd1234\n",
                        replyPattern="(abc.)(\\d{4})")
            self.assertEqual(firstGroup, "abcd")
            self.assertEqual(secondGroup, "1234")

        def testFailedWriteStringReadMatchingPattern(self):
            with self.assertRaises(CommunicationReadNoMatch) as context:
                reply = self.port.writeStringExpectMatchingString(
                            "abcd1234\n",
                            replyPattern="abc.\\d{5}")

        def testFailedWriteStringReadMatchingPatternFirstCaptureGroup(self):
            with self.assertRaises(CommunicationReadNoMatch) as context:
                firstGroup = self.port.writeStringReadFirstMatchingGroup(
                            "abcd1234\n",
                            replyPattern="abc.(\\d{5})")

        def testFailedWriteStringReadMatchingPatternWithoutGroupFirstCaptureGroup(self):
            with self.assertRaises(CommunicationReadNoMatch) as context:
                firstGroup = self.port.writeStringReadFirstMatchingGroup(
                            "abcd1234\n",
                            replyPattern="abc.\\d{4}")

        def testFailedWriteStringReadMatchingPatternAllCaptureGroups(self):
            with self.assertRaises(CommunicationReadNoMatch) as context:
                (firstGroup, secondGroup) = self.port.writeStringReadMatchingGroups(
                            "abcd1234\n",
                            replyPattern="(abc.)(\\d{5})")

        def testThreadSafety(self):
            global threadFailed
            threadFailed = -1
            threadPool = []
            for i in range(100):
                process = Thread(target=threadReadWrite, kwargs=dict(port=self.port, index=i))
                process.start()
                threadPool.append(process)

            for i,t in enumerate(threadPool):
                t.join(timeout=2)

                try:
                    globalLock.acquire()
                    if threadFailed != -1:
                        self.fail("Thread {0}?".format(threadFailed))
                finally:
                    globalLock.release()

        
def threadReadWrite(port, index):
    global threadFailed
    payload = "abcd{0}\n".format(index)
    globalLock.acquire()
    try:
        port.writeStringExpectMatchingString(payload, replyPattern=payload)
    except:
        if threadFailed != -1:
            threadFailed = index        
    finally:
        globalLock.release()




class TestDebugEchoPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        self.port = DebugEchoSerialPort()
        self.assertIsNotNone(self.port)
        self.port.open()

    def tearDown(self):
        self.port.close()


class TestRealEchoPort(BaseTestCases.TestEchoPort):

    def setUp(self):
        try:
            self.port = SerialPort("/dev/cu.usbserial-ftDXIKC4")
            self.assertIsNotNone(self.port)
            self.port.open()
        except:
            self.fail("Unable to setUp serial port")


    def tearDown(self):
        self.port.close()


if __name__ == '__main__':
    unittest.main()
