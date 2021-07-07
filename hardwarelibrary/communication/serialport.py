from .communicationport import *
import time
from serial.tools.list_ports import comports
import re
import pyftdi.serialext
import pyftdi.ftdi 

class UnableToOpenSerialPort(serial.SerialException):
    pass

class MoreThanOneMatch(serial.SerialException):
    pass

class SerialPort(CommunicationPort):
    """
    An implementation of CommunicationPort using BSD-style serial port
    
    Two strategies to initialize the SerialPort:
    1. with a portPath/port name (i.e. "COM1" or "/dev/cu.serial")
    2. with an instance of pyserial.Serial() that will support the same
       functions as pyserial.Serial() (open, close, read, write, readline)
    3. with a URL for support through pyftdi to access the chip directly. Use portPath 'ftdi://ftdi:2232h/2'
       or the find_url.py script from the distribution. More info: https://eblot.github.io/pyftdi/api/usbtools.html
       You have to add any custom VID/PID when using tools (but they are added here in SerialPort) @line 30.
    """
    def __init__(self, idVendor=None, idProduct=None, serialNumber=None, portPath=None, port=None):
        CommunicationPort.__init__(self)

        try:
            pyftdi.ftdi.Ftdi.add_custom_product(vid=idVendor, pid=idProduct, pidname='VID {0}: PID {1}'.format(idVendor, idProduct))
        except ValueError as err:
            # It is not an error: it is already registered
            pass

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

    @property
    def portPathIsURL(self):
        if re.match(r"^ftdi://", self.portPath, re.IGNORECASE):
            return True
        return False

    def open(self, baudRate=57600, timeout=0.3):
        if self.port is None:
            if self.portPathIsURL:
                # See https://eblot.github.io/pyftdi/api/uart.html
                self.port = pyftdi.serialext.serial_for_url(self.portPath, baudrate=baudRate, timeout=timeout)
            else:
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
