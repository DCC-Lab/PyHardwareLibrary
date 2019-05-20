from PhysicalDevice import *
from CommunicationPort import *
import numpy as np

class LaserSourceDevice:
    def __init__():
        self.requestedPower = 0
        self.power = 0

    def turnOn():
        self.doTurnOn()

    def turnOff():
        self.doTurnOff()

    def setPower(power:float):
        self.doSetPower(power)

    def power() -> float:
        return self.doGetPower()

class CoboltDevice(PhysicalDevice, LaserSourceDevice):

    def __init__(bsdPath=None, serialNumber: str = None,
                 productId: np.uint32 = None, vendorId: np.uint32 = None):

        self.port = CommunicationPort(bsdPath=bsdPath)
        PhysicalDevice.__init__(vendorId, productId, serialNumber)
        LaserSourceDevice.__init__()

    def doInitializeDevice():
        self.port.open()
        return

    def doShutdownDevice():
        self.port.close()
        return