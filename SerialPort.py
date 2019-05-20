import serial
import re
from threading import Thread, RLock

class CommunicationReadTimeout(serial.SerialException):
    pass

class CommunicationReadNoMatch(Exception):
    pass

class SerialPort:
    """SerialPort class with basic application-level protocol 
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
        self.portLock.acquire()
        try:
            data = self.port.read(length)
            if len(data) != length:
                raise CommunicationReadTimeout()

        finally:
            self.portLock.release()

        return data

    def writeData(self, data):
        self.portLock.acquire()
        try:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
            self.port.flush()
        finally:
            self.portLock.release()

        return nBytesWritten

    def readString(self):
        self.portLock.acquire()
        try:
            byte = None
            data = bytearray(0)
            while (byte != b''):
                byte = self.readData(1)
                data += byte
                if byte == b'\n':
                    break

            string = data.decode(encoding='utf-8')
        finally:
            self.portLock.release()

        return string

    def writeString(self, string):
        self.portLock.acquire()
        nBytes = 0
        try:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data)
        finally:
            self.portLock.release()

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern):
        self.transactionLock.acquire()

        try:
            self.writeString(string)
            reply = self.readString()
            match = re.search(replyPattern, string)
            if match is None:
                raise CommunicationReadNoMatch("No match")
        finally:
            self.transactionLock.release()

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern):
        self.transactionLock.acquire()

        try:
            groups = self.writeStringReadMatchingGroups(string, replyPattern)
            if len(groups) >= 1:
                return groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}'".format(replyPattern))
        finally:
            self.transactionLock.release()

    def writeStringReadMatchingGroups(self, string, replyPattern):
        self.transactionLock.acquire()

        try:
            self.writeString(string)
            reply = self.readString()
            match = re.search(replyPattern, string)

            if match is not None:
                return match.groups()
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))
        finally:
            self.transactionLock.release()


class DebugEchoSerialPort(SerialPort):
    def __init__(self):
        self.buffer = bytearray()
        super(DebugEchoSerialPort, self).__init__()

    def open(self):
        return

    def close(self):
        return

    def bytesAvailable(self):
        return len(self.buffer)

    def readData(self, length):
        self.portLock.acquire()
        try:
            data = bytearray()
            for i in range(0, length):
                if len(self.buffer) > 0:
                    byte = self.buffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")
        finally:
            self.portLock.release()

        return data

    def writeData(self, data):
        self.portLock.acquire()
        try:
            self.buffer.extend(data)
        finally:
            self.portLock.release()

        return len(data)
