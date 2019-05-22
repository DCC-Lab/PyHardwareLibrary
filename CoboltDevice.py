from PhysicalDevice import *
from CommunicationPort import *
import numpy as np
# from typing import Protocol


class LaserSourceDevice:
    def __init__(self):
        self.requestedPower = 0
        self.power = 0

    def turnOn(self):
        self.doTurnOn()

    def turnOff(self):
        self.doTurnOff()

    def setPower(self, power:float):
        self.doSetPower(power)

    def power(self) -> float:
        return self.doGetPower()


class CoboltDevice(PhysicalDevice, LaserSourceDevice):
    def __init__(self, bsdPath=None, serialNumber: str = None,
                 productId: np.uint32 = None, vendorId: np.uint32 = None):
        self.laserSerialNumber = None
        self.port = CommunicationPort(bsdPath=bsdPath)
        PhysicalDevice.__init__(self, vendorId, productId, serialNumber)
        LaserSourceDevice.__init__(self)

    def doInitializeDevice(self):
        try:
            self.port.open()
            self.doGetLaserSerialNumber()
        except Exception as error:
            self.port.close()
            raise error

    def doShutdownDevice(self):
        self.port.close()
        return

    def doGetLaserSerialNumber(self):
        self.laserSerialNumber = self.port.writeStringReadFirstMatchingGroup("sn?\r", replyPattern="(\\d+)")
