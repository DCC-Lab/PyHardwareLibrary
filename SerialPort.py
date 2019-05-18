import errno
import fcntl
import os
import select
import struct
import sys
import termios
import array
import math
import serial #pyserial
import re

class SerialPort:
    """SerialPort class with basic application-level protocol functions to write strings and read strings"""
    port = None
    bsdPath = None
    vendorId = None
    productId = None
    serialNumber = None

    def __init__(self, bsdPath = None, vendorId = None, productId = None, serialNumber = None):
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
        return nBytesWritten

    def readString(self):
        byte = None
        data = bytearray(0)
        while ( byte != b''):
            byte = self.readData(1)
            data += byte
            if byte == b'\n':
                break

        string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string):
        data = bytearray(string, "utf-8")
        return self.port.write(data)

    def writeReadMatch(self, string, replyPattern):
        self.writeString(string)
        reply = self.readString()
        match = re.search(replyPattern, string)
        
        return match is not None


        


if __name__ == "__main__":
    port = SerialPort("/dev/cu.usbserial-ftDXIKC4")
    port.open()
    port.writeString("abcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd\n")
    print(port.readString())
    print(port.writeReadMatch(string="abcd\n", replyPattern="abcd"))
    print(port.writeReadMatch(string="abcd\n", replyPattern="abcad"))
    port.close()
