import time
from abc import abstractmethod
from enum import Enum

from hardwarelibrary.communication import USBPort, TextCommand
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class PowerMeterNotification(Enum):
    didMeasure     = "didMeasure"

class PowerMeterDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.absolutePower = 0

    # capabilities() / hasCapability() are inherited from PhysicalDevice.

    # Measuring absolute power is the one capability every power meter has, so
    # its hook stays on the base; optional capabilities live in mixins.
    @abstractmethod
    def doGetAbsolutePower(self):
        ...

    def measureAbsolutePower(self):
        self.doGetAbsolutePower()
        power = self.absolutePower
        NotificationCenter().postNotification(PowerMeterNotification.didMeasure, notifyingObject=self, userInfo=power)
        return power

    def doGetStatusUserInfo(self):
        return self.measureAbsolutePower()
