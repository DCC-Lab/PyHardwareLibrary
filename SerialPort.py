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


class SerialPort:
    """SerialPort class with basic application-level protocol 
    functions to write strings and read strings"""
    port = None
    bsdPath = None
    vendorId = None
    productId = None
    serialNumber = None

    def __init__(self, bsdPath=None, vendorId=None,
                 productId=None, serialNumber=None):
        self.bsdPath = bsdPath

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
        data = self.port.read(length)
        return data

    def writeData(self, data):
        nBytesWritten = self.port.write(data)
        if nBytesWritten != len(data):
            raise IOError("Not all bytes written to port")

    def readString(self):
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
        data = bytearray(string, "utf-8")
        self.writeData(data)

    def writeStringExpectMatchingString(self, string, replyPattern):
        self.writeString(string)
        reply = self.readString()
        match = re.search(replyPattern, string)
        if match is None:
            raise RuntimeError("No match")

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern):
        groups = self.writeStringReadMatchingGroups(string, replyPattern)
        if len(groups) >= 1:
            return match.group(1)
        else:
            raise RuntimeError("No match")

    def writeStringReadMatchingGroups(self, string, replyPattern):
        self.writeString(string)
        reply = self.readString()
        match = re.search(replyPattern, string)

        if match is not None:
            return match.groups()
        else:
            raise RuntimeError("No match")


class DebugEchoSerialPort(SerialPort):
    buffer = bytearray()

    def open(self):
        return

    def close(self):
        return

    def readData(self, length):
        data = bytearray()
        for i in range(0, length):
            byte = self.buffer.pop(0)
            data.append(byte)

        return data

    def writeData(self, data):
        self.buffer.extend(data)
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
