import serial
import re
import time
import random
from threading import Thread, RLock

class CommunicationReadTimeout(serial.SerialException):
    pass

class CommunicationReadNoMatch(Exception):
    pass

class CommunicationPort:
    """CommunicationPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.

    Two strategies to initialize the CommunicationPort:
    1. with a bsdPath/port name (i.e. "COM1" or "/dev/cu.serial")
    2. with an instance of SerialPort() that will support the same
       functions as pyserial.Serial() (open, close, read, write, readline)
    """
    
    def __init__(self, bsdPath=None, port = None):
        self.bsdPath = bsdPath
        self.port = port # direct port , must be closed.

        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        return self.port.is_open    

    def open(self):
        if self.port is None:
            self.port = serial.Serial(self.bsdPath, 19200, timeout=0.3)
        else:
            self.port.open()

    def close(self):
        self.port.close()

    def bytesAvailable(self) -> int:
        return self.port.in_waiting

    def flush(self):
        self.port.reset_input_buffer()
        self.port.reset_output_buffer()

    def readData(self, length) -> bytearray:
        with self.portLock:
            data = self.port.read(length)
            if len(data) != length:
                raise CommunicationReadTimeout()

        return data

    def writeData(self, data) -> int:
        with self.portLock:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
            self.port.flush()

        return nBytesWritten

    def readString(self) -> str:      
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

    def writeString(self, string) -> int:
        nBytes = 0
        with self.portLock:
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
                return match.groups()
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))


