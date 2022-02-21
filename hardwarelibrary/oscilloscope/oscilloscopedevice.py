import time
from enum import Enum
from hardwarelibrary.communication import USBPort, TextCommand
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class Channels(Enum):
    ch1     = "ch1"
    ch2     = "ch2"

class OscilloscopeDevice(PhysicalDevice):

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        super().__init__(serialNumber, idProduct, idVendor)

    def getWaveform(self, channel):
        return None

    def getTimeScale(self):
        return None

    def getVoltageScale(self):
        return None

    def doGetStatusUserInfo(self):
        return None
