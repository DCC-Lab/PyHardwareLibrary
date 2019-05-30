from .PhysicalDevice import *
from .LinearMotionDevice import *

from .CommunicationPort import *

import numpy as np
import re
import time
from collections import namedtuple

class SutterDevice(PhysicalDevice, LinearMotionDevice):

    def __init__(self, bsdPath=None, portPath=None, serialNumber: str = None,
                 productId: np.uint32 = None, vendorId: np.uint32 = None):

        if bsdPath is not None:
            self.portPath = bsdPath
        elif portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        PhysicalDevice.__init__(self, serialNumber, vendorId, productId)
        LinearMotionDevice.__init__(self)
        self.port = None
        self.xMinLimit = 0
        self.yMinLimit = 0
        self.zMinLimit = 0
        self.xMaxLimit = 25000
        self.yMaxLimit = 25000
        self.zMaxLimit = 25000


    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def doInitializeDevice(self): 
        try:
            if self.portPath == "debug":
                self.port = CommunicationPort(port=SutterDebugSerial())
            else:
                self.port = CommunicationPort(portPath=self.portPath)
            
            if self.port is None:
                raise PhysicalDeviceUnableToInitialize("Cannot allocate port {0}".format(self.portPath))

            self.port.open()
            self.port.doGetPosition()

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDeviceUnableToInitialize()
        except PhysicalDeviceUnableToInitialize as error:
            raise error
        

    def doShutdownDevice(self):
        self.port.close()
        self.port = None
        return

class CommandString:
    def __init__(self, name, pattern):
        self.text = ""
        self.name = name
        self.pattern = pattern
        self.groups = ()

    def match(self, inputString) -> Match:
        return re.search(self.pattern, inputString)

class CommandData:
    def __init__(self, name, hexPattern, dataLength):
        self.data = bytearray()
        self.name = name
        self.hexPattern = hexPattern
        self.dataLength = dataLength
        self.groups = ()

    def match(self, inputData) -> Match:
        inputHexString = inputData.hex()
        return re.search(self.hexPattern, inputHexString)

class DebugCommunicationPort:
    def __init__(self):
        self.outputBuffer = bytearray()
        self.lineEnding = b'\r'
        self.commands = ()
        self._isOpen = True

    @property
    def is_open(self):
        return self._isOpen
    
    def open(self):
        with globalLock:
            if self._isOpen:
                raise IOError("port is already open")
            else:
                self._isOpen = True

        return

    def close(self):
        with globalLock:
            self._isOpen = False

        return

    def flush(self):
        return

    def read(self, length) -> bytearray:
        with globalLock:
            data = bytearray()
            for i in range(0, length):
                if len(self.outputBuffer) > 0:
                    byte = self.outputBuffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data


    def write(self, data:bytearray) -> int :
        inputString = data.decode('utf-8')
        replyData = bytearray()
        for command in self.commands:
            match = re.search(command.pattern, inputString)
            if match is not None:
                replyData = self.processCommand(command, match.groups(), inputString)
                self.outputBuffer.append(replyData)
                break

        return len(replyData)

    def loadCommands(self):
        move = CommandData(name='move', hexPattern=b'M')
        position = CommandData(name='position', hexPattern=b'C')
        self.commands.append(move)
        self.commands.append(position)

    def processCommand(self, command, groups, inputString) -> bytearray:
        if self.commands is None:
            self.loadCommands()

        if command.name == 'move':
            self.x = float(groups[0])
            self.y = float(groups[1])
            self.z = float(groups[2])
            return b'0'
        elif command.name == 'position':
            replyData = bytearray()
            replyData.expand(bytearray(struct.pack("f", self.x)))
            replyData.expand(bytearray(struct.pack("f", self.y)))
            replyData.expand(bytearray(struct.pack("f", self.z)))

            return replyData
