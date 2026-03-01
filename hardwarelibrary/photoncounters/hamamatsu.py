from enum import Enum, IntEnum
import hardwarelibrary.utils
from hardwarelibrary.notificationcenter import NotificationCenter
from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.communication.usbport import *
from struct import *

class HamamatsuH11890Device(PhysicalDevice):
    classIdVendor = 0x0661
    classIdProduct = 0x3705

    class BadCommand(Exception):
        pass

    class Overload(Exception):
        pass

    def __init__(self):
        PhysicalDevice.__init__(self, serialNumber="*", idVendor=0x0661, idProduct = 0x3705)

    def doInitializeDevice(self):
        self.port = USBPort(idVendor=0x0661, idProduct = 0x3705)
        self.port.open()
        self.stop_counting() # We must stop counting first
        self.turn_on()
        self.set_integration_time(time_in_10us=1000)

    def doShutdownDevice(self):
        self.stop_counting()
        self.turn_off()
        self.port.close()

    def sendCommand(self, commandName, payload=None):
        commandInt = None
        if payload is None:
            commandData = commandName.encode("utf-8")
        else:
            commandInt = ord(commandName)
            commandData = pack("<II",ord(commandName), payload)

        self.port.writeData(commandData)
        replyInt, value = self.readReply()
        if replyInt == 0x4342:
            raise HamamatsuH11890Device.BadCommand()

        return replyInt, value

    def readReply(self):
        replyData = self.port.readData(64)
        replyData = replyData[0:8]
        return unpack("<II", replyData)

    def get_integration_time(self):
        return self.sendCommand("I")

    def set_integration_time(self, time_in_10us):
        return self.sendCommand(commandName="I", payload=time_in_10us)

    def get_repetition(self):
        return self.sendCommand(commandName='R')

    def set_repetition(self, repetitions=0):
        return self.sendCommand(commandName="R", payload=repetitions)

    def turn_on(self):
        self.set_high_voltage()

    def turn_off(self):
        self.set_high_voltage(value=0)

    def get_high_voltage(self):
        return self.sendCommand("V")

    def set_high_voltage(self, value=None):
        if value is None: 
            return self.sendCommand("DV") # Default high voltage

        return self.sendCommand("V", value)

    def start_counting(self, correction=True):
        if correction:
            return self.port.writeData(b'M')
        else:
            return self.port.writeData(b'C')

    def fetchAll(self, maxIndex=None):
        counts = []
        while True:
            index, count = self.fetchOne()
            if index is None:
                break
            counts.append( (index, count,) )
        return counts

    def fetchOne(self):
        idx = None
        count = None

        try:
            idx, count = self.readReply()
        except usb.core.USBTimeoutError as err:
            return None, None

        if (count & 0x8000) != 0:
            raise HamamatsuH11890Device.Overload()

        return idx, count


    def stop_counting(self):
        self.port.writeData(b'\r')
        self.port.flush()
