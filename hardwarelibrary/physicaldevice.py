from enum import Enum, IntEnum
from hardwarelibrary.notificationcenter import NotificationCenter
import typing

class DeviceState(IntEnum):
    Unconfigured = 0 # Dont know anything
    Ready = 1        # Connected and initialized
    Recognized = 2   # Initialization has succeeded, but currently shutdown
    Unrecognized = 3 # Initialization failed

class PhysicalDeviceNotification(Enum):
    willInitializeDevice       = "willInitializeDevice"
    didInitializeDevice        = "didInitializeDevice"
    willShutdownDevice         = "willShutdownDevice"
    didShutdownDevice          = "didShutdownDevice"

class PhysicalDevice:
    class UnableToInitialize(Exception):
        pass
    class UnableToShutdown(Exception):
        pass
    class ClassIncompatibleWithRequestedDevice(Exception):
        pass

    classIdVendor = None
    classIdProduct = None

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        if serialNumber == "*" or serialNumber is None:
            serialNumber = ".*"
        if idProduct is None:
            idProduct = self.classIdProduct
        if idVendor is None:
            idVendor = self.classIdVendor

        if not self.isCompatibleWith(serialNumber, idProduct, idVendor):
            raise PhysicalDevice.ClassIncompatibleWithRequestedDevice()

        self.idVendor = idVendor
        self.idProduct = idProduct
        self.serialNumber = serialNumber
        self.state = DeviceState.Unconfigured

        self.usbDevice = None

    @classmethod
    def candidates(cls, idVendor, idProduct):
        candidateClasses = []
        
        if cls.isCompatibleWith(serialNumber="*", idProduct=idProduct, idVendor=idVendor):
            candidateClasses.append(cls) 

        for aSubclass in cls.__subclasses__():
            candidateClasses.extend(aSubclass.candidates(idVendor, idProduct))

        return candidateClasses

    @classmethod
    def isCompatibleWith(cls, serialNumber, idProduct, idVendor):
        if idVendor == cls.classIdVendor and idProduct == cls.classIdProduct:
            return True

        return False
    
    def initializeDevice(self):
        if self.state != DeviceState.Ready:
            try:
                NotificationCenter().postNotification(PhysicalDeviceNotification.willInitializeDevice, notifyingObject=self)
                self.doInitializeDevice()
                self.state = DeviceState.Ready
                NotificationCenter().postNotification(PhysicalDeviceNotification.didInitializeDevice, notifyingObject=self)
            except Exception as error:
                self.state = DeviceState.Unrecognized
                NotificationCenter().postNotification(PhysicalDeviceNotification.didInitializeDevice, notifyingObject=self, userInfo=error)
                raise PhysicalDevice.UnableToInitialize(error)

    def doInitializeDevice(self):
        raise NotImplementedError("Base class must override doInitializeDevice()")

    def shutdownDevice(self):
        if self.state == DeviceState.Ready:
            try:
                NotificationCenter().postNotification(PhysicalDeviceNotification.willShutdownDevice, notifyingObject=self)
                self.doShutdownDevice()
                NotificationCenter().postNotification(PhysicalDeviceNotification.didShutdownDevice, notifyingObject=self)
            except Exception as error:
                NotificationCenter().postNotification(PhysicalDeviceNotification.didShutdownDevice, notifyingObject=self, userInfo=error)
                raise PhysicalDevice.UnableToShutdown(error)
            finally:
                self.state = DeviceState.Recognized

    def doShutdownDevice(self):
        raise NotImplementedError("Base class must override doShutdownDevice()")
