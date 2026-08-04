import time
from abc import abstractmethod
from enum import Enum

from hardwarelibrary.capabilities import notifies
from hardwarelibrary.communication import USBPort, TextCommand
from hardwarelibrary.physicaldevice import *
from notificationcenter import NotificationCenter, Notification

class PowerMeterNotification(Enum):
    # Named after the hook, like every capability: measureAbsolutePower is a
    # read, so it posts a did only.
    didGetAbsolutePower = "didGetAbsolutePower"

class PowerMeterDevice(PhysicalDevice):
    notification = PowerMeterNotification

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)
        self.absolutePower = 0

    # capabilities() / hasCapability() are inherited from PhysicalDevice.

    # Measuring absolute power is the one capability every power meter has, so
    # its hook stays on the base; optional capabilities live in mixins.
    @abstractmethod
    def doGetAbsolutePower(self):
        ...

    @notifies(did=PowerMeterNotification.didGetAbsolutePower)
    def measureAbsolutePower(self):
        self.doGetAbsolutePower()
        return self.absolutePower

    def doGetStatusUserInfo(self):
        return self.measureAbsolutePower()
