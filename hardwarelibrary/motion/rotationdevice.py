from abc import abstractmethod
from enum import Enum

from hardwarelibrary.capabilities import notifies
from hardwarelibrary.physicaldevice import *
from notificationcenter import NotificationCenter, Notification

class RotationMotionNotification(Enum):
    # moveTo, moveBy and home share one pair, as in LinearMotionNotification: the
    # user_info carries the angle or the delta, and neither for home.
    willMove          = "willMove"
    didMove           = "didMove"
    didGetOrientation = "didGetOrientation"

class Direction(Enum):
    unidirectional = "unidirectional"
    bidirectional  = "bidirectional"

class RotationDevice(PhysicalDevice):
    notification = RotationMotionNotification

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.theta = None

    # Hardware hooks a driver must implement, on top of doInitializeDevice
    # and doShutdownDevice inherited from PhysicalDevice.
    @abstractmethod
    def doMoveTo(self, angle):
        ...

    @abstractmethod
    def doMoveBy(self, deltaTheta):
        ...

    @abstractmethod
    def doGetOrientation(self) -> float:
        ...

    @abstractmethod
    def doHome(self):
        ...

    @notifies(will=RotationMotionNotification.willMove,
              did=RotationMotionNotification.didMove)
    def moveTo(self, angle):
        self.doMoveTo(angle)

    @notifies(will=RotationMotionNotification.willMove,
              did=RotationMotionNotification.didMove)
    def moveBy(self, deltaTheta):
        self.doMoveBy(deltaTheta)

    @notifies(did=RotationMotionNotification.didGetOrientation)
    def orientation(self) -> ():
        return self.doGetOrientation()

    @notifies(will=RotationMotionNotification.willMove,
              did=RotationMotionNotification.didMove)
    def home(self) -> ():
        self.doHome()


class DebugRotationDevice(RotationDevice):
    classIdProduct = 0xfffd
    classIdVendor = debugClassIdVendor
    def __init__(self):
        super().__init__("debug", DebugRotationDevice.classIdProduct, DebugRotationDevice.classIdVendor)
        self._debugOrientation = 0

    def doGetOrientation(self) -> float:
        return self._debugOrientation

    def doMoveTo(self, angle):
        self._debugOrientation = angle

    def doMoveBy(self, displacement):
        self._debugOrientation += displacement

    def doHome(self):
        self._debugOrientation = 0

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass