import usb.core
import usb.util
from communicationport import *
import re
import time
import random
from threading import Thread, RLock


class USBPort(CommunicationPort):
    """USBPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.
    """
    
    def __init__(self, idVendor=None, idProduct=None, interfaceNumber=0):
        CommunicationPort.__init__(self)

        self.device = usb.core.find(idVendor=idVendor)
        if self.device is None:
            raise IOError("Can't find device")

        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()

        self.interface = self.configuration[(interfaceNumber,0)]
        self.outputEndPoint = [None, None, None, None, None]
        self.outputEndPoint[1] = self.interface[0]
        self.inputEndPoint = [None, None, None, None, None]
        self.inputEndPoint[1] = self.interface[1]

        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        if self.mainOut is None:
            return False    
        else:
            return True    

    def open(self):
        return

    def close(self):
        return

    def bytesAvailable(self) -> int:
        return 0

    def flush(self):
        return

    def readData(self, length, endPoint=1) -> bytearray:
        with self.portLock:
            data = self.inputEndPoint[endPoint].read(size_or_buffer=length)
            if len(data) != length:
                raise CommunicationReadTimeout()

        return data

    def writeData(self, data, endPoint=1) -> int:
        with self.portLock:
            nBytesWritten = self.outputEndPoint[endPoint].write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")

        return nBytesWritten


class DebugEchoCommunicationPort(CommunicationPort):
    def __init__(self, delay=0):
        self.buffer = bytearray()
        self.delay = delay
        self._isOpen = False
        super(DebugEchoCommunicationPort, self).__init__()

    @property
    def isOpen(self):
        return self._isOpen    

    def open(self):
        if self._isOpen:
            raise Exception()

        self._isOpen = True
        return

    def close(self):
        self._isOpen = False
        return

    def bytesAvailable(self):
        return len(self.buffer)

    def flush(self):
        self.buffer = bytearray()

    def readData(self, length):
        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.buffer) > 0:
                    byte = self.buffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data):
        with self.portLock:
            self.buffer.extend(data)

        return len(data)
