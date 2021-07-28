from hardwarelibrary.physicaldevice import *
import numpy as np

class LinearMotionDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, productId:np.uint32, vendorId:np.uint32):
        super().__init__(serialNumber, productId, vendorId)
        self.x = None
        self.y = None
        self.z = None
        self.xMinLimit = None
        self.yMinLimit = None
        self.zMinLimit = None
        self.xMaxLimit = None
        self.yMaxLimit = None
        self.zMaxLimit = None


    def moveTo(self, x=None, y=None, z=None):
        self.doMoveTo(x, y, z)

    def position(self) -> ():
        return self.doGetPosition()

    def move1DTo(self, x):
        self.doMoveTo(x)

    def move2DTo(self, x, y):
        self.doMoveTo(x, y)

    def move3DTo(self, x, y, z):
        self.doMoveTo(x, y, z)

    def position1D(self) -> (float):
        return self.doGetPosition()

    def position3D(self) -> (float, float):
        return self.doGetPosition()

    def position3D(self) -> (float, float, float):
        return self.doGetPosition()

class DebugLinearMotionDevice(LinearMotionDevice):

    def __init__(self):
        super().__init__("debug", 0xffff, 0xfffd)

    def doGetPosition(self) -> (float, float, float):
        return (self.x, self.y, self.z)

    def doMoveTo(self, x, y, z):
        (self.x, self.y, self.z) = (x,y,z)

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass