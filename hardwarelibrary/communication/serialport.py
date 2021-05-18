from .communicationport import *
import time

class UnableToOpenSerialPort(serial.SerialException):
    pass

class SerialPort(CommunicationPort):
    """
    An implementation of CommunicationPort using BSD-style serial port
    
    Two strategies to initialize the SerialPort:
    1. with a bsdPath/port name (i.e. "COM1" or "/dev/cu.serial")
    2. with an instance of pyserial.Serial() that will support the same
       functions as pyserial.Serial() (open, close, read, write, readline)
    """
    def __init__(self, bsdPath=None, portPath=None, port = None):
        CommunicationPort.__init__(self, )
        if bsdPath is not None:
            self.portPath = bsdPath
        elif portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        if port is not None and port.is_open:
            port.close()
            
        self.port = None # direct port, must be closed.

        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        if self.port is None:
            return False    
        else:
            return self.port.is_open    

    def open(self):
        if self.port is None:
            self.port = serial.Serial(self.portPath, 57600, timeout=0.3)
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
            time.sleep(0.05)
            self.port.flushInput()
            self.port.flushOutput()
            time.sleep(0.05)

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
