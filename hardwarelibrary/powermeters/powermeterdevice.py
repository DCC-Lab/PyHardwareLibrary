import time
from abc import abstractmethod
from enum import Enum

from hardwarelibrary.communication import USBPort, TextCommand
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from hardwarelibrary.powermeters.capabilities import Capability

class PowerMeterNotification(Enum):
    didMeasure     = "didMeasure"

class PowerMeterDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.absolutePower = 0

    def capabilities(self) -> list:
        # The capability mixins, not the marker nor the device class itself
        # (a driver is a Capability subclass too, but it is a PhysicalDevice).
        return [klass for klass in type(self).__mro__
                if issubclass(klass, Capability)
                and klass is not Capability
                and not issubclass(klass, PhysicalDevice)]

    def hasCapability(self, capabilityClass) -> bool:
        return isinstance(self, capabilityClass)

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
