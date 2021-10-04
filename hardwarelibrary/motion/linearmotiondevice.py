from enum import Enum
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class LinearMotionNotification(Enum):
    willMove       = "willMove"
    didMove        = "didMove"
    didGetPosition = "didGetPosition"

class Direction(Enum):
    unidirectional = "unidirectional"
    bidirectional  = "bidirectional"

class LinearMotionDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
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
        NotificationCenter().postNotification(LinearMotionNotification.willMove, notifyingObject=self, userInfo=position)
        self.doMoveTo(position)
        NotificationCenter().postNotification(LinearMotionNotification.didMove, notifyingObject=self, userInfo=position)

    def moveBy(self, displacement):
        NotificationCenter().postNotification(LinearMotionNotification.willMove, notifyingObject=self, userInfo=displacement)
        self.doMoveBy(displacement)
        NotificationCenter().postNotification(LinearMotionNotification.didMove, notifyingObject=self, userInfo=displacement)

    def position(self) -> ():
        position = self.doGetPosition()
        NotificationCenter().postNotification(LinearMotionNotification.didGetPosition, notifyingObject=self, userInfo=position)
        return position

    def home(self) -> ():
        NotificationCenter().postNotification(LinearMotionNotification.willMove, notifyingObject=self)
        self.doHome()
        NotificationCenter().postNotification(LinearMotionNotification.didMove, notifyingObject=self)

    def moveInMicronsTo(self, position):
        nativePosition = [x * self.nativeStepsPerMicrons for x in position]
        self.moveTo(nativePosition)

    def moveInMicronsBy(self, displacement):
        nativeDisplacement = [dx * self.nativeStepsPerMicrons for dx in displacement]
        self.moveTo(nativeDisplacement)

    def positionInMicrons(self):
        position = self.position()
        positionInMicrons = [x / self.nativeStepsPerMicrons for x in position]
        return tuple(positionInMicrons)

    def mapPositions(self, width: int, height: int, stepInMicrons: float, direction: Direction = Direction.unidirectional):
        """mapPositions(width, height, stepInMicrons[, direction == "leftRight" or "zigzag"])

        Returns a list of position tuples, which can be used directly in moveTo functions, to map a sample."""

        (initWidth, initHeight, depth) = self.positionInMicrons()
        mapPositions = []
        for j in range(height):
            y = initHeight + j * stepInMicrons
            if Direction(direction) == Direction.unidirectional:
                for i in range(width):
                    x = initWidth + i*stepInMicrons
                    index = (i, j)
                    position = (x, y, depth)
                    info = {"index": index, "position": position}
                    mapPositions.append(info)
            elif Direction(direction) == Direction.bidirectional:
                if j % 2 == 0:
                    for i in range(width):
                        x = initWidth + i * stepInMicrons
                        index = (i, j)
                        position = (x, y, depth)
                        info = {"index": index, "position": position}
                        mapPositions.append(info)
                elif j % 2 == 1:
                    for i in range(width-1, -1, -1):
                        x = initWidth + i * stepInMicrons
                        index = (i, j)
                        position = (x, y, depth)
                        info = {"index": index, "position": position}
                        mapPositions.append(info)
            else:
                raise ValueError("Invalid direction: {0}".format(direction))
        return mapPositions


class DebugLinearMotionDevice(LinearMotionDevice):
    classIdProduct = 0xfffd
    classIdVendor = 0xffff
    def __init__(self):
        super().__init__("debug", DebugLinearMotionDevice.classIdProduct, DebugLinearMotionDevice.classIdVendor )
        (self.x, self.y, self.z) = (0, 0, 0)
        self.nativeStepsPerMicrons = 16

    def doGetPosition(self) -> (float, float, float):
        return (self.x, self.y, self.z)

    def doMoveTo(self, position):
        x, y, z = position
        (self.x, self.y, self.z) = (x, y, z)

    def doMoveBy(self, displacement):
        dx, dy, dz = displacement
        self.x += dx
        self.y += dy 
        self.z += dz

    def doHome(self):
        (self.x, self.y, self.z) = (0, 0, 0)

    def doInitializeDevice(self):
        pass

    def doShutdownDevice(self):
        pass