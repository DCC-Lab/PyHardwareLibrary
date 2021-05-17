import time
import random

from hardwarelibrary.communication import *
from threading import Thread, Lock

class DebugPort(CommunicationPort):
    def __init__(self, delay=0):
        self.buffers = [bytearray(),bytearray()]
        self.delay = delay
        self._isOpen = False
        super(DebugPort, self).__init__()

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

    def bytesAvailable(self, endPoint=0):
        return len(self.buffers[endPoint])

    def flush(self):
        self.buffers = [bytearray(),bytearray()]

    def readData(self, length, endPoint=None):
        if endPoint is None:
            endPointIndex = 0

        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.buffers[endPointIndex]) > 0:
                    byte = self.buffers[endPointIndex].pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data, endPoint=None):
        if endPoint is None:
            endPointIndex = 0

        with self.portLock:
            self.buffers[endPointIndex].extend(data)

        return len(data)

class DebugEchoPort(DebugPort):
    def __init__(self, delay=0):
        super(DebugEchoPort, self).__init__(delay=delay)

    def readData(self, length, endPoint=None):
        if endPoint is None:
            endPointIndex = 0

        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.buffers[endPointIndex]) > 0:
                    byte = self.buffers[endPointIndex].pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data, endPoint=None):
        if endPoint is None:
            endPointIndex = 0

        with self.portLock:
            self.buffers[endPointIndex].extend(data)

        return len(data)
