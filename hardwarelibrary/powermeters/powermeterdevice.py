from enum import Enum
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class PowerMeterNotification(Enum):
    didMeasure     = "didMeasure"

class PowerMeterDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.absolutePower = 0
        self.calibrationWavelength = None

    def measureAbsolutePower(self):
        self.doGetAbsolutePower()
        power = self.absolutePower
        NotificationCenter().postNotification(PowerMeterNotification.didMeasure, notifyingObject=self, userInfo=power)
        return power

    def doGetAbsolutePower(self):

class IntegraDevice(PowerMeterDevice):
    classIdProduct = 0x0300
    classIdVendor = 0x1ad5

    def __init__(self, serialNumber:str = None, idProduct:int = IntegraDevice.classIdProduct, idVendor:int = IntegraDevice.classIdVendor):
        self.port = None

    def doInitializeDevice(self):
        self.port = USBPort(idVendor=self.idVendor, idProduct=self.idProduct, interfaceNumber=0, defaultEndPoints=(1, 2))
        self.port.open()

    def doShutdownDevice(self):
        self.port.close()
        self.port = None