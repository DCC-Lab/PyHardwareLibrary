from PhysicalDevice import *
from CommunicationPort import *
import numpy as np
from CoboltDebugSerial import *
import re

class LaserSourceDevice:

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

        self.laserPower = 0
        self.requestedPower = 0
        self.interlockState = True
        self.laserSerialNumber = None


        self.bsdPath = bsdPath
        PhysicalDevice.__init__(self, serialNumber, vendorId, productId)
        LaserSourceDevice.__init__(self)
        self.port = None


    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def doInitializeDevice(self): 
        try:
            if self.bsdPath == "debug":
                self.port = CommunicationPort(port=CoboltDebugSerial())
            else:
                self.port = CommunicationPort(bsdPath=bsdPath)

            # print("Port {0}".format(self.port))
            # if self.port is None:
            #     raise ValueError()

            self.port.open()
        except Exception as error:
            self.port.close()
            raise error

    def doShutdownDevice(self): # Doesn't seem to do anything
        self.port.close()
        return

    def doGetInterlockState(self) -> bool:
        value = self.port.writeStringExpectMatchingString('ilk?\r', replyPattern='([0|1])')
        self.interlockState = bool(value)

    def doGetLaserSerialNumber(self):
        self.laserSerialNumber = self.port.writeStringReadFirstMatchingGroup('sn?\r', replyPattern='(\\d+)')

    def doTurnOn(self):
        self.port.writeString('l1\r')

    def doTurnOff(self): # The laser needs to be unplug after using this function or it doesn't restart using doTurnOn??
        self.port.writeString('l0\r')

    def doSetPower(self, powerInWatts):
        command = 'p {0:0.3f}\r'.format(powerInWatts)
        self.port.writeString(command)

    def doGetPower(self):
        value = self.port.writeStringReadFirstMatchingGroup('pa?\r', replyPattern='(\\d.\\d+)')
        return float(value)

if __name__ == "__main__":
    laser = None
    try:
        laser = CoboltDevice("debug")
    except:
        print("No laser found on COM5. Using debug")
        laser = CoboltDevice("debug")

    laser.initializeDevice()
    laser.turnOn()
    laser.setPower(0.1)
    print(laser.power())
    laser.setPower(0.01)
    print(laser.power())
    laser.setPower(0.2)
    print(laser.power())
    laser.turnOff()
    laser.shutdownDevice()


#laser.doTurnOn()
#laser.doGetLaserSerialNumber()
#laser.doGetPower()
#laser.doGetInterlockState()
#laser.doSetPower(powerInWatts=0.01)
#print("Power is %f W" % laser.doGetPower())
