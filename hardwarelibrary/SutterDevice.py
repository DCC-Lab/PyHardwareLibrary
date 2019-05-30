from .PhysicalDevice import *
from .LinearMotionDevice import *

from .CommunicationPort import *

import numpy as np
import re
import time

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
