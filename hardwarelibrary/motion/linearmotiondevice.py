from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter
import numpy as np
from enum import Enum

class Notification(Enum):
    willMove       = "willMove"
    didMove        = "didMove"
    didGetPosition = "didGetPosition"

class LinearMotionDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, productId:np.uint32, vendorId:np.uint32):
        super().__init__(serialNumber, productId, vendorId)
        self.x = None
        self.y = None
        self.z = None
        self.nativeStepsPerMicrons = 1
        self.xMinLimit = None
        self.yMinLimit = None
        self.zMinLimit = None
        self.xMaxLimit = None
        self.yMaxLimit = None
        self.zMaxLimit = None

    def moveTo(self, position):
        NotificationCenter().postNotification(Notification.willMove.value, notifyingObject=self, userInfo=position)
        self.doMoveTo(position)
        NotificationCenter().postNotification(Notification.didMove.value, notifyingObject=self, userInfo=position)

    def moveBy(self, displacement):
        NotificationCenter().postNotification(Notification.willMove.value, notifyingObject=self, userInfo=displacement)
        self.doMoveBy(displacement)
        NotificationCenter().postNotification(Notification.didMove.value, notifyingObject=self, userInfo=displacement)

    def position(self) -> ():
        position = self.doGetPosition()
        NotificationCenter().postNotification(Notification.didGetPosition.value, notifyingObject=self, userInfo=position)
        return position

    def home(self) -> ():
        NotificationCenter().postNotification(Notification.willMove.value, notifyingObject=self)
        self.doHome()
        NotificationCenter().postNotification(Notification.didMove.value, notifyingObject=self)

    def moveInMicronsTo(self, position):
        nativePosition = [ x * self.nativeStepsPerMicrons for x in position]
        self.moveTo(nativePosition)

    def moveInMicronsBy(self, displacement):
        nativeDisplacement = [ dx * self.nativeStepsPerMicrons for dx in displacement]
        self.moveTo(nativeDisplacement)

    def positionInMicrons(self):
        position = self.position()
        positionInMicrons = [ x / self.nativeStepsPerMicrons for x in position]
        return positionInMicrons

class DebugLinearMotionDevice(LinearMotionDevice):

    def __init__(self):
        super().__init__("debug", 0xffff, 0xfffd)
        (self.x, self.y, self.z) = (0,0,0)
        self.nativeStepsPerMicrons = 16

    def doGetPosition(self) -> (float, float, float):
        return (self.x, self.y, self.z)

    def doMoveTo(self, position):
        x, y, z = position
        (self.x, self.y, self.z) = (x,y,z)

    def doMoveBy(self, displacement):
        dx, dy, dz = displacement
        self.x += dx
        self.y += dy 
        self.z += dz

    def doHome(self):
        (self.x, self.y, self.z) = (0,0,0)

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass