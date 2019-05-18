import errno
import fcntl
import os
import select
import struct
import sys
import termios

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
        self.fd = os.open(self.bsdPath, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

        if self.fd != -1:
            try:
                value = fcntl.ioctl(self.fd, fcntl.F_SETFL, fcntl.ioctl(self.fd, fcntl.F_GETFL,0))
                if  value & ~os.O_NONBLOCK == -1:
                    raise ValueError(-1)
            except OSError as msg:
                print(msg)

    def close(self):
        os.close(self.fd)

    def readData(self, length):
        data = os.read(self.fd, length)
        return data

    def writeData(self, data):
        nBytesWritten = os.write(self.fd, data)
        return nBytesWritten

    def readString(self):
        byte = None
        data = bytearray(0)
        while ( byte != "\n"):
            byte = self.readData(1)
            if byte == b'':
                break
            else:
                data += byte

        string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string):
        data = bytearray(string, "utf-8")
        return os.write(self.fd, data)
        


if __name__ == "__main__":
    port = SerialPort("/dev/null")
    port.open()
    port.writeString("abcd")
    print(port.readData(1))
    port.close()
