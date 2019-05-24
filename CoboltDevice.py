from PhysicalDevice import *
from LaserSourceDevice import *

from CommunicationPort import *
from CoboltDebugSerial import *

import numpy as np
import re

class CoboltCantTurnOnWithAutostartOn(Exception):
    pass

class CoboltDevice(PhysicalDevice, LaserSourceDevice):

    def __init__(self, bsdPath=None, serialNumber: str = None,
                 productId: np.uint32 = None, vendorId: np.uint32 = None):

        self.laserPower = 0
        self.requestedPower = 0
        self.interlockState = None
        self.autostart = None
        self.laserSerialNumber = None
        self.isOn = None

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
    def autostartIsOn(self) -> bool:
        self.doGetAutostart()
        return self.autostart

    def turnAutostartOn(self):
        self.doTurnAutostartOn()

    def turnAutostartOff(self):
        self.doTurnAutostartOff()

    def doInitializeDevice(self): 
        try:
            if self.bsdPath == "debug":
                self.port = CommunicationPort(port=CoboltDebugSerial())
            else:
                self.port = CommunicationPort(bsdPath=self.bsdPath)
            
            if self.port is None:
                raise PhysicalDeviceUnableToInitialize("Cannot allocate port {0}".format(self.bsdPath))

            self.port.open()
            self.doGetLaserSerialNumber()
            self.doGetAutostart()
            self.doTurnAutostartOn()
            self.doGetInterlockState()
            self.doGetPower()
        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDeviceUnableToInitialize()
        except PhysicalDeviceUnableToInitialize as error:
            raise error
        

    def doShutdownDevice(self):
        self.port.close()
        self.port = None
        return

    def doGetInterlockState(self) -> bool:
        value = self.port.writeStringExpectMatchingString('ilk?\r', replyPattern='(0|1)')
        self.interlockState = bool(value)
        return self.interlockState

    def doGetLaserSerialNumber(self) -> str:
        self.laserSerialNumber = self.port.writeStringReadFirstMatchingGroup('sn?\r', replyPattern='(\\d+)')

    def doGetOnOffState(self) -> bool:
        value = self.port.writeStringExpectMatchingString('l?\r', replyPattern='(0|1)')
        self.isOn = (int(value) == 1)
        return self.isOn        

    def doTurnOn(self):
        if not self.doGetAutostart():
            self.port.writeStringExpectMatchingString('l1\r', replyPattern='OK')
        else:
            raise CoboltCantTurnOnWithAutostartOn()

    def doTurnOff(self):
        self.port.writeStringExpectMatchingString('l0\r', replyPattern='OK')

    def doGetAutostart(self) -> bool:
        value = self.port.writeStringReadFirstMatchingGroup('@cobas?\r', '([1|0])')
        self.autostart = (int(value) == 1)
        return self.autostart

    def doTurnAutostartOn(self):
        self.port.writeStringExpectMatchingString('@cobas 1\r', 'OK')
        self.autostart = True

    def doTurnAutostartOff(self):
        self.port.writeStringExpectMatchingString('@cobas 0\r', 'OK')
        self.autostart = False

    def doSetPower(self, powerInWatts):
        command = 'p {0:0.3f}\r'.format(powerInWatts)
        self.port.writeStringExpectMatchingString(command, replyPattern='OK')

    def doGetPower(self) -> float:
        value = self.port.writeStringReadFirstMatchingGroup('pa?\r', replyPattern='(\\d.\\d+)')
        return float(value)
