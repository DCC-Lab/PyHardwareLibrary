from PhysicalDevice import *
from CommunicationPort import *
import numpy as np


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
        PhysicalDevice.__init__(self, serialNumber, vendorId, productId)
        LaserSourceDevice.__init__(self)
        self.port.open()

    def __del__(self):
        if self.port is not None:
            self.port.close()

    def doInitializeDevice(self): # Doesn't work well, seems to know that the port is already open
        try:
            self.port.open()
            self.doGetLaserSerialNumber()
        except Exception as error:
            self.port.close()
            raise error

    def doShutdownDevice(self): # Doesn't seem to do anything
        self.port.close()
        return

    def doGetInterlockState(self):
        self.port.writeStringExpectMatchingString('ilk?\r', replyPattern='[0|1]')

    def doGetLaserSerialNumber(self):
        self.laserSerialNumber = self.port.writeStringExpectMatchingString('sn?\r', replyPattern='(\\d+)')

    def doTurnOn(self):
#        self.port.writeStringExpectMatchingString('@cobas 0\r', '')
        self.port.writeStringExpectMatchingString('l1\r', '')

    def doTurnOff(self): # The laser needs to be unplug after using this function or it doesn't restart using doTurnOn??
        self.port.writeStringExpectMatchingString('l0\r', '')

    def doSetPower(self, powerInWatts):
        command = 'p {0:0.3f}\r'.format(powerInWatts)
        self.port.writeStringExpectMatchingString(command, '')

    def doGetPower(self):
        self.port.writeStringExpectMatchingString('pa?\r', replyPattern='\d.\d+')


if __name__ == "__main__":
    try:
        laser = CoboltDevice("COM5")
    except:
        exit("No laser found on COM5")

laser.doTurnOn()
#laser.doTurnOn()
#laser.doGetLaserSerialNumber()
#laser.doGetPower()
#laser.doGetInterlockState()
#laser.doSetPower(powerInWatts=0.01)
#print("Power is %f W" % laser.doGetPower())
