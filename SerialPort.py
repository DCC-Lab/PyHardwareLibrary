import errno
import fcntl
import os
import select
import struct
import sys
import termios

class CommunicationPort:

    def readData(self, length, matching=".*"):
        """ Primitive: read data of 'length' """
        raise NotImplementedError("Subclasses must implement readData()")

    def writeData(self, data):
        """ Primitive: write data packet """
        raise NotImplementedError("Subclasses must implement writeData()")

    def readString(self, matching=".*"):
        return ()

    def writeString(self, string):
        return

class SerialPort(CommunicationPort):
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
        try:
            self.fd = os.open(self.bsdPath, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)

            if self.fd == -1:
                raise ValueError(-1)

            try:
                value = fcntl.ioctl(self.fd, fcntl.F_SETFL, fcntl.ioctl(self.fd, fcntl.F_GETFL,0))
                if  value & ~os.O_NONBLOCK == -1:
                    raise ValueError(-1)
            except Exception:
                pass


        except OSError as msg:
            self.fd = None
            raise SerialException(msg.errno, "could not open port {}: {}".format(self._port, msg))
        # ~ fcntl.fcntl(self.fd, fcntl.F_SETFL, 0)  # set blocking

        print("Open")
        return None

    def close(self):
        print("Close")
        return None

if __name__ == "__main__":
    port = SerialPort("/dev/null")
    port.open()
    port.close()
