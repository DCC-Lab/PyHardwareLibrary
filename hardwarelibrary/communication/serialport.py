from .communicationport import *
import time
from serial.tools.list_ports import comports
import re

class UnableToOpenSerialPort(serial.SerialException):
    pass

class MoreThanOneMatch(serial.SerialException):
    pass

class SerialPort(CommunicationPort):
    """
    An implementation of CommunicationPort using BSD-style serial port
    
    Two strategies to initialize the SerialPort:
    1. with a bsdPath/port name (i.e. "COM1" or "/dev/cu.serial")
    2. with an instance of pyserial.Serial() that will support the same
       functions as pyserial.Serial() (open, close, read, write, readline)
    """
    def __init__(self, idVendor=None, idProduct=None, serialNumber=None, portPath=None, port=None):
        CommunicationPort.__init__(self)

        if idVendor is not None:
            portPath = SerialPort.matchAnyPort(idVendor, idProduct, serialNumber)

        if portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        if port is not None and port.is_open:
            port.close()
            
        self.port = None # direct port, must be closed.

    @classmethod
    def matchSinglePort(cls, idVendor=None, idProduct=None, serialNumber=None):
        ports = cls.matchPorts(idVendor, idProduct, serialNumber)
        if len(ports) == 1:
            return ports[0]
        return None

    @classmethod
    def matchAnyPort(cls, idVendor=None, idProduct=None, serialNumber=None):
        ports = cls.matchPorts(idVendor, idProduct, serialNumber)
        if len(ports) >= 1:
            return ports[0]
        return None

    @classmethod
    def matchPorts(cls, idVendor=None, idProduct=None, serialNumber=None):
        # We must provide idVendor, idProduct and serialNumber
        # or              idVendor and idProduct
        # or              idVendor
        ports = []
        for port in comports():
            if idProduct is None:
                if port.vid == idVendor:
                    ports.append(port.device)
            elif serialNumber is None:
                if port.vid == idVendor and port.pid == idProduct:
                    ports.append(port.device)
            else:
                if port.vid == idVendor and port.pid == idProduct:
                    if re.match(serialNumber, port.serial_number, re.IGNORECASE):
                        ports.append(port.device)
        return ports

    @property
    def isOpen(self):
        if self.port is None:
            return False    
        else:
            return self.port.is_open    

    def open(self, baudRate=57600, timeout=0.3):
        if self.port is None:
            self.port = serial.Serial(self.portPath, baudRate, timeout=timeout)
        else:
            self.port.open()

        timeoutTime = time.time() + 0.5
        while not self.isOpen:
            time.sleep(0.05)
            if time.time() > timeoutTime:
                raise UnableToOpenSerialPort()
        time.sleep(0.05)

    def close(self):
        self.port.close()

    def bytesAvailable(self) -> int:
        return self.port.inWaiting()

    def flush(self):
        if self.isOpen:
            # When an FTDI chip is used, this short sleep delay appears necessary
            # If not, the flush does not occur.
            time.sleep(0.02)
            self.port.flushInput()
            self.port.flushOutput()
            time.sleep(0.02)

    def readData(self, length, endPoint=0) -> bytearray:
        with self.portLock:
            data = self.port.read(length)
            if len(data) != length:
                raise CommunicationReadTimeout("Only obtained {0}".format(data))

        return data

    def writeData(self, data, endPoint=0) -> int:
        with self.portLock:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
            self.port.flush()

        return nBytesWritten
