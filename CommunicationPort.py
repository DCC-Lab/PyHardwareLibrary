import serial
import re
from threading import Thread, RLock
import time
import random

class CommunicationReadTimeout(serial.SerialException):
    pass

class CommunicationReadNoMatch(Exception):
    pass

class CommunicationPort:
    """CommunicationPort class with basic application-level protocol 
    functions to write strings and read strings"""
    port = None
    def __init__(self, bsdPath=None, vendorId=None,
                 productId=None, serialNumber=None):
        self.bsdPath = bsdPath
        self.vendorId = vendorId
        self.productId = productId
        self.serialNumber = serialNumber
        self.portLock = RLock()
        self.transactionLock = RLock()


    def open(self):
        self.port = serial.Serial(self.bsdPath, 19200, timeout=0.3)

    def close(self):
        self.port.close()

    def bytesAvailable(self):
        return self.port.in_waiting

    def readData(self, length):
        with self.portLock:
            data = self.port.read(length)
            if len(data) != length:
                raise CommunicationReadTimeout()

        return data

    def writeData(self, data):
        with self.portLock:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
            self.port.flush()

        return nBytesWritten

    def readString(self):      
        with self.portLock:
            byte = None
            data = bytearray(0)
            while (byte != b''):
                byte = self.readData(1)
                data += byte
                if byte == b'\n':
                    break

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string):
        with self.portLock:
            nBytes = 0
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data)

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern):
        with self.transactionLock:
            self.writeString(string)
            reply = self.readString()
            match = re.search(replyPattern, reply)
            if match is None:
                raise CommunicationReadNoMatch("No match")

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern):
        with self.transactionLock:
            groups = self.writeStringReadMatchingGroups(string, replyPattern)
            if len(groups) >= 1:
                return groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}'".format(replyPattern))

    def writeStringReadMatchingGroups(self, string, replyPattern):
        with self.transactionLock:
            self.writeString(string)
            reply = self.readString()
            match = re.search(replyPattern, reply)

            if match is not None:
                print(match.groups())
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))


class DebugEchoCommunicationPort(CommunicationPort):
    def __init__(self, delay=0):
        self.buffer = bytearray()
        self.delay = delay
        super(DebugEchoCommunicationPort, self).__init__()

    def open(self):
        return

    def close(self):
        return

    def bytesAvailable(self):
        return len(self.buffer)

    def readData(self, length):
        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.buffer) > 0:
                    byte = self.buffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data):
        with self.portLock:
            self.buffer.extend(data)

        return len(data)
