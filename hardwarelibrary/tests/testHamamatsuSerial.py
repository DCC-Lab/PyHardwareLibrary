import env
import unittest
from struct import *

from hardwarelibrary.communication.usbport import *

class TestHamamatsuUSBPortBase(unittest.TestCase):
    def setUp(self):
        self.port = USBPort(idVendor=0x0661, idProduct = 0x3705)
        self.assertIsNotNone(self.port)
        self.port.open()
        self.assertTrue(self.port.isOpen)

        self.port.writeData(b'\r')
        self.port.flush()
        
    def tearDown(self):
        # self.port.writeData(b"ZV")
        # self.assertEqual("ZV", self.readStringFromPMT())
        self.port.close()


    def test01CreatePort(self):
        self.assertIsNotNone(self.port)

    def test02OpenPort(self):
        self.assertTrue(self.port.isOpen)

    def test03SendDVCommand(self):
        """
        This helped me figure out that the readData command would always
        read 64 bytes.
        """
        self.port.writeString(string="DV")
        count = 64
        while count > 0:
            try:
                print(count, self.port.readData(1))
            except Exception as err:
                print(err)
                break
            count = count -1

    @unittest.expectedFailure
    def test04SendDVZVCommand(self):
        """
        This never worked.
        """

        self.port.writeString(string="DV")
        count = 64
        while count > 0:
           try:
               print(count, self.port.readData(1))
           except Exception as err:
               print(err)
               break
           count = count -1

        self.port.writeString(string="ZV")
        count = 64
        while count > 0:
           try:
               print(count, self.port.readData(1))
           except Exception as err:
               print(err)
               break
           count = count -1

    def test05SendDVZeroCommand(self):
        """

        """

        self.port.writeData(b"DV\x00")
        data = self.port.readData(64)
        string = data.decode("utf-8")
        for i,c in enumerate(string):
           if c == '\x00':
               string = string[:i]
               break
        self.port.close()

    def test06UseFunctionValidCommand(self):
        """
        I created a function to read the pmt, it is flawed
        but up to here it works.
        """
        self.port.writeData(b"DV")
        reply = self.readStringFromPMT()
        self.assertEqual("DV", reply)

    def test07UseFunctionInvalidCommand(self):
        """
        I figured out with these tests that BC is bad command
        """

        self.port.writeData(b"DV\n")
        reply = self.readStringFromPMT()
        self.assertEqual("BC", reply)

    def test07TurnOn(self):
        """
        This never worked, I understood the manual was not useful much.
        I checked with various suffixes, but the DV needed to be 2 bytes
        """

        commands = self.extendCommand("DV")
        self.validate(commands)

    def test07TurnOff(self):
        """
        This never worked, I figured out it was not a command.
        I checked with various suffixes, but but nothing worked
    """
        commands = self.extendCommand("ZV")
        are_valid = self.validate(commands)
        self.assertTrue(any(are_valid))

        commands = self.extendCommand("zv")
        are_valid = self.validate(commands)
        self.assertTrue(any(are_valid))

        for i, is_valid in enumerate(are_valid):
            print(commands[i], is_valid)

    def testFind2Letter_Commands(self):
        """
        I brute forced it: what are the 2-letter commands?
        I checked all combinations and checked to see if it complained 'BC'
        If it did not I assumed this meant it is a command (which is wrong, see
        later).
        """
        for c1 in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
            for c2 in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
                commands = self.extendCommand(c1+c2)

                replies, are_valid = self.validate(commands)

                for i, is_valid in enumerate(are_valid):
                    if is_valid:
                        print(commands[i], replies[i])

    def testFind1Letter_Commands(self):
        """
        I noticed that after 'C' I started getting stuff regularly.
        I figured 'C' was starting the count like in the documentatin
        but I needed to figure out how to understand the output.
        """
        for c1 in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ":
            commands = self.extendCommand(c1)
            replies, are_valid = self.validate(commands)

            for i, is_valid in enumerate(are_valid):
                if is_valid:
                    print(commands[i], replies[i])

    def testFind1Byte_Commands(self):
        """
        Just in case, checked binary but no: nothing new
        """
        valid = []
        for c1 in range(128):
            print("{0:x}".format(c1))
            if chr(c1) == 'D':
                continue

            commands = [chr(c1)]

            replies, are_valid = self.validate(commands)

            for i, is_valid in enumerate(are_valid):
                if is_valid:
                    print(commands[i], replies[i])
                    valid.append(commands[i])

        print(valid)

    def testFind2Byte_Commands(self):
        """
        Same
        """
        for c1 in range(256):
            print("-",c1)
            for c2 in range(256):
                commands = self.extendCommand(chr(c1)+chr(c2))

                replies, are_valid = self.validate(commands)

                for i, is_valid in enumerate(are_valid):
                    if is_valid:
                        print(commands[i], replies[i])

    def validate(self, commands):
        are_valid = []
        replies = []
        one_valid = False
        for command in commands:
            try:
                self.port.flush()
                self.port.writeData(command)
                reply = self.readStringFromPMT()
                if reply != "BC":
                    are_valid.append(True)
                else:
                    are_valid.append(False)
                replies.append(reply)
            except Exception as err:
                are_valid.append(False)
                replies.append(None)

        return replies, are_valid

        #     self.port.writeData(b"\r")

    def test08start_counting(self):
        """
        Here, I printed the read data for a while and noticed
        an indexed value going up by one. And some weird garbage values after.        
        """
        self.port.defaultTimeout = 5000

        self.port.writeData(b"C")

        count = 0
        while count < 4:
            try:
                replyData = self.port.readData(64)
                print(replyData)
                count += 1
            except Exception as err:
                print(err)
                count += 1
                pass


    def test08GetIntegrationTimeself(self):
        """
        Here, I noticed the 'I' command appeared valid in my long list of attempts.
        I printed the reply data for a while and noticed
        an value corresponding to the letter 'I', a few zeros. And some weird garbage values after.
        
        Eventually, I figured it out: the first 32 bits are the command letter ASCII
        code in a lttle endian 32-bit integer, and then the integration time also as a 32 bit
        integer. But then, the nuber was 100 000, not 1000 as expected. I assumed
        this meant my model was in 10µs units.

        So 'I' replied with 'I',0x00,0x00,0x00,0xa0,0x86,0x01,0x00
        So I decided to try to send the same command back on the next test.
        """
        self.port.writeData(b"I")
        replyData = self.port.readData(64)
        replyData = replyData[0:8]
        print(replyData)
        index, photonCount = unpack("<II", replyData)

        print(chr(index), photonCount)

    def test09SetIntegrationTimeself(self):
        """
        Knowing that 'I' replied with 'I',0x00,0x00,0x00,0xa0,0x86,0x01,0x00
        I decided to try to send the same command back: it worked.
        I started changing the value of the 32-bit integer to see what happened.
        For that I needed to test the 'C' command again.
        """
        self.port.writeData(b'I   \x10\x27\x00\x00')
        replyData = self.port.readData(64)
        replyData = replyData[0:8]
        print(replyData)
        index, photonCount = unpack("<II", replyData)

        print(index, photonCount)

    def test10start_countingProperly(self):
        """
        Finally, this appears perfect.
        """
        self.port.defaultTimeout = 5000

        self.port.writeData(b"C")

        count = 0
        while count < 10:
            try:
                replyData = self.port.readData(64)
                replyData = replyData[0:8]
                index, photonCount = unpack("<II", replyData)
                print(index, photonCount)
                count += 1
            except Exception as err:
                print(err)
                pass

        self.port.writeData(b"\r")

    def test09Extension(self):
        commands = self.extendCommand("DV")
        self.assertTrue(len(commands) == 6)

    def test20GetRepCounter(self):
        self.port.writeData(b"R")
        replyData = self.port.readData(64)
        replyData = replyData[0:8]
        index, photonCount = unpack("<II", replyData)
        print("Repetition:", index, photonCount)

    def test20SetRepCounter(self):
        self.port.writeData(b"R\x00\x00\x00\x10\x00\x00\x00")
        replyData = self.port.readData(64)
        replyData = replyData[0:8]
        index, photonCount = unpack("<II", replyData)
        print("Set rep {0:x} {1:x} {2}".format(index, photonCount, chr(index)))

    def extendCommand(self, command):
        suffixes = [b"", b"\r", b"\n", b"\r\n", b"\n\r", b"\x00"]

        if type(command) == str:
            commandData = command.encode("utf-8")
        else:
            commandData = command

        return [ commandData + suffix for suffix in suffixes]

    def readStringFromPMT(self):
        data = self.port.readData(64)
        string = ""
        for i,c in enumerate(data):
            if c == 0:
                break
                
            string += chr(c) # assume utf-8

        return string

if __name__ == '__main__':
    unittest.main()
