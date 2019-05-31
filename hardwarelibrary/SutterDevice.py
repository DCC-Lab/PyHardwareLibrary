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
                self.port = SutterDebugSerialPort()
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

class SutterDebugSerialPort(DebugCommunicationPort):
    def __init__(self):
        DebugCommunicationPort.__init__()
        move = CommandData(name='move', hexPattern='..(........)(........)(........)')
        position = CommandData(name='position', hexPattern=b'C')
        self.commands.append(move)
        self.commands.append(position)

    def processCommand(self, command, groups, inputData) -> bytearray:
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
