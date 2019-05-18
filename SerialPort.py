import errno
import fcntl
import os
import select
import struct
import sys
import termios
import array
import math

class SerialPort:
    """SerialPort class with basic application-level protocol functions to write strings and read strings"""
    fd = None
    bsdPath = None
    vendorId = None
    productId = None
    serialNumber = None

    def __init__(self, bsdPath = None, vendorId = None, productId = None, serialNumber = None):
        self.bsdPath = bsdPath

    def flush(self):
        return None

    def drain(self):
        return None

    def open(self):
        self.fd = os.open(self.bsdPath, os.O_RDWR | os.O_NOCTTY)

        # flag = fcntl.fcntl(self.fd, fcntl.F_GETFL,0)
        # fcntl.fcntl(self.fd, fcntl.F_SETFL, flag & ~os.O_NONBLOCK)

    def close(self):
        os.close(self.fd)

    def bytesAvailable(self):
        bytes = bytearray(4)
        arg = 0
        n = fcntl.fcntl(self.fd, termios.FIONREAD, arg)

        print(n, arg)
        return bytes

    def readData(self, length):
        bytesAvailable = self.bytesAvailable()

        if length <= bytesAvailable:
            data = os.read(self.fd, length)
        else:
            data = os.read(self.fd, bytesAvailable)
        return data

    def writeData(self, data):
        nBytesWritten = os.write(self.fd, data)
        return nBytesWritten

    def readString(self):
        byte = None
        data = bytearray(0)
        while ( byte != b''):
            byte = self.readData(1)
            if byte == b'\n':
                break
            else:
                data += byte

        string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string):
        data = bytearray(string, "utf-8")
        return os.write(self.fd, data)
        


if __name__ == "__main__":
    port = SerialPort("/dev/cu.usbserial-ftDXIKC4")
    port.open()
    port.writeString("abcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcdabcd")
    print(port.readData(8))
    port.close()
