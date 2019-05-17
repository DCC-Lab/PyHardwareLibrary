import errno
import fcntl
import os
import select
import struct
import sys
import termios

class SerialPort:
    """SerialPort class with basic application-level protocol functions to write strings and read strings"""
    port = None
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
        try:
            self.port = open(self.bsdPath, "r+")
        except OSError as msg:
            self.port = None
            raise SerialException(msg.errno, "could not open port {}: {}".format(self.port, msg))

    def close(self):
        self.port.close()

    def readString(self, matching=".*"):
        string = self.port.readline()
        return string

    def writeString(self, string):
        return self.port.write(string)
        


if __name__ == "__main__":
    port = SerialPort("/dev/null")
    port.open()
    port.writeString("abcd")
    string = port.readString()
    port.close()
