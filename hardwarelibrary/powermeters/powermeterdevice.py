import time
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
        self.calibrationWavelength = None

    def measureAbsolutePower(self):
        self.doGetAbsolutePower()
        power = self.absolutePower
        NotificationCenter().postNotification(PowerMeterNotification.didMeasure, notifyingObject=self, userInfo=power)
        return power

    def getCalibrationWavelength(self):
        self.doGetCalibrationWavelength()
        return self.calibrationWavelength

    def setCalibrationWavelength(self, wavelength):
        self.doSetCalibrationWavelength(wavelength)
        self.doGetCalibrationWavelength()

    def measureAbsolutePower(self):
        self.doGetAbsolutePower()
        power = self.absolutePower
        NotificationCenter().postNotification(PowerMeterNotification.didMeasure, notifyingObject=self, userInfo=power)
        return power

    def doGetStatusUserInfo(self):
        return self.measureAbsolutePower()
