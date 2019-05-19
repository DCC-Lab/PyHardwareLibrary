import errno
import fcntl
import os
import select
import struct
import sys
import termios
import array
import math
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
        self.lock = RLock()

    def open(self):
        self.port = serial.Serial(self.bsdPath, 19200, timeout=1)

    def close(self):
        self.port.close()

    def bytesAvailable(self):
        return self.port.inwaiting()

    def flush(self):
        return None

    def drain(self):
        return None

    def readData(self, length):
        self.lock.acquire()
        try:
            data = self.port.read(length)
        finally:
            self.lock.acquire()

        return data

    def writeData(self, data):
        self.lock.acquire()
        try:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
        finally:
            self.lock.acquire()

        return nBytesWritten

    def readString(self):
        self.lock.acquire()
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
            self.lock.release()

        return string

    def writeString(self, string):
        self.lock.acquire()
        nBytes = 0
        try:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data)
        finally:
            self.lock.release()

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern):
        self.writeString(string)
        reply = self.readString()
        match = re.search(replyPattern, string)
        if match is None:
            raise CommunicationReadNoMatch("No match")

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern):
        groups = self.writeStringReadMatchingGroups(string, replyPattern)
        if len(groups) >= 1:
            return groups[0]
        else:
            raise CommunicationReadNoMatch("No match")

    def writeStringReadMatchingGroups(self, string, replyPattern):
        self.writeString(string)
        reply = self.readString()
        match = re.search(replyPattern, string)

        if match is not None:
            return match.groups()
        else:
            raise CommunicationReadNoMatch("No match")


class DebugEchoSerialPort(SerialPort):
    def __init__(self):
        self.buffer = bytearray()
        super(DebugEchoSerialPort, self).__init__()

    def open(self):
        return

    def close(self):
        return

    def readData(self, length):
        self.lock.acquire()
        try:
            data = bytearray()
            for i in range(0, length):
                if len(self.buffer) > 0:
                    byte = self.buffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")
        finally:
            self.lock.release()

        return data

    def writeData(self, data):
        self.lock.acquire()
        try:
            self.buffer.extend(data)
        finally:
            self.lock.release()

        return len(data)


if __name__ == "__main__":
    port = DebugEchoSerialPort()
    port.open()
    port.close()

    # port = SerialPort("/dev/cu.usbserial-ftDXIKC4")
    # port.open()
    # port.writeString("abcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd\n")
    # print(port.readString())
    # print(port.writeStringExpectMatchingString(string="abcd\n", replyPattern="abcd"))
    # print(port.writeStringExpectMatchingString(string="abcd\n", replyPattern="abcad"))
    # print(port.writeStringReadFirstMatchingGroup(string="abcd\n", replyPattern="ab(cd)"))
    # port.close()
