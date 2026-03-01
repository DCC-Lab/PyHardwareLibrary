import time
import random

from hardwarelibrary.communication import *
from threading import Thread, Lock

class DebugPort(CommunicationPort):
    def __init__(self, delay=0, numberOfEndPoints=1):
        self.inputBuffers = [bytearray() for _ in range(numberOfEndPoints)]
        self.outputBuffers = [bytearray() for _ in range(numberOfEndPoints)]
        self.delay = delay
        self.defaultTimeout = 500
        self._isOpen = False
        super(DebugPort, self).__init__()

    @property
    def isOpen(self):
        return self._isOpen

    def open(self):
        if self._isOpen:
            raise Exception("Port already open")

        self._isOpen = True

    def close(self):
        self._isOpen = False

    def bytesAvailable(self, endPoint=0):
        endPointIndex = endPoint if endPoint is not None else 0
        return len(self.outputBuffers[endPointIndex])

    def flush(self):
        for i in range(len(self.inputBuffers)):
            self.inputBuffers[i] = bytearray()
        for i in range(len(self.outputBuffers)):
            self.outputBuffers[i] = bytearray()

    def readData(self, length, endPoint=None):
        endPointIndex = endPoint if endPoint is not None else 0

        with self.portLock:
            if self.delay > 0:
                time.sleep(self.delay * random.random())

            data = bytearray()
            for i in range(length):
                if len(self.outputBuffers[endPointIndex]) > 0:
                    byte = self.outputBuffers[endPointIndex].pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read {0} bytes, only {1} available".format(length, len(data)))

        return data

    def writeData(self, data, endPoint=None):
        endPointIndex = endPoint if endPoint is not None else 0

        with self.portLock:
            self.inputBuffers[endPointIndex].extend(data)

        self.processInputBuffers(endPointIndex=endPointIndex)

        return len(data)

    def writeToOutputBuffer(self, data, endPointIndex=0):
        self.outputBuffers[endPointIndex].extend(data)

    def processInputBuffers(self, endPointIndex):
        # We default to ECHO for simplicity
        inputBytes = self.inputBuffers[endPointIndex]

        # Do something, here we do an Echo
        self.writeToOutputBuffer(inputBytes, endPointIndex)
        self.inputBuffers[endPointIndex] = bytearray()