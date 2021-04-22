from .communicationport import *

import usb.core
import usb.util
import re
import time
import random
from threading import Thread, RLock
import array

class USBPort(CommunicationPort):
    """USBPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.
    """
    @classmethod
    def allDevices(cls, verbose=False):
        for bus in usb.busses():
            for device in bus.devices:
                if device != None:
                    usbDevice = usb.core.find(idVendor=device.idVendor, idProduct=device.idProduct)
                    print("{2}, {3} ({0:04x}, {1:04x})".format(usbDevice.idVendor, usbDevice.idProduct, usbDevice.manufacturer, usbDevice.product))
                    for conf in usbDevice:
                        print("  conf #:{0}, num of interfaces: {1}".format(conf.bConfigurationValue, conf.bNumInterfaces))                        
                        for intf in conf:
                            print("    #int:{0} #endpoints: {1}".format(intf.bInterfaceNumber, intf.bNumEndpoints))

        if verbose:
            for bus in usb.busses():
                for device in bus.devices:
                    if device != None:
                        usbDevice = usb.core.find(idVendor=device.idVendor, idProduct=device.idProduct)
                        print(usbDevice)

    def __init__(self, idVendor=None, idProduct=None, serialNumber=None, interfaceNumber=0, defaultEndPoints=(0, 1)):
        CommunicationPort.__init__(self)
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.serialNumber = serialNumber
        self.interfaceNumber = interfaceNumber
        self.defaultEndPointsIndex = defaultEndPoints

        self.device = None
        self.configuration = None
        self.interface = None        
        self.defaultOutputEndPoint = None
        self.defaultInputEndPoint = None

        self._internalBuffer = bytearray()

    def __del__(self):
        """ We need to make sure that the device is free for others to use """
        if self.device is not None:
            self.device.reset()

    @property
    def isOpen(self):
        if self.device is None:
            return False    
        else:
            return True    
    @property
    def isNotOpen(self):
        return not self.isOpen

    def open(self):
        self._internalBuffer = bytearray()

        self.device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.device is None:
            raise IOError("Can't find device")

        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(self.interfaceNumber,0)]
        
        outputIndex, inputIndex = self.defaultEndPointsIndex
        self.defaultOutputEndPoint = self.interface[outputIndex]
        self.defaultInputEndPoint = self.interface[inputIndex]

    def close(self):
        self._internalBuffer = None
        
        if self.device is not None:
            self.device.reset()
            self.device = None
            self.configuration = None
            self.interface = None        
            self.defaultOutputEndPoint = None
            self.defaultInputEndPoint = None

    def bytesAvailable(self, endPoint=None) -> int:
        return len(self._internalBuffer)

    def flush(self, endPoint=None):
        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        else:
            inputEndPoint = self.interface[endPoint]
        
        with self.portLock:
            self._internalBuffer = bytearray()
            maxPacket = inputEndPoint.wMaxPacketSize
            data = array.array('B',[0]*maxPacket)
            nBytesRead = inputEndPoint.read(size_or_buffer=data, timeout=30)
            self._internalBuffer += bytearray(data[:nBytesRead])

    def readData(self, length, endPoint=None) -> bytearray:
        if not self.isOpen:
            self.open()

        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        else:
            inputEndPoint = self.interface[endPoint]

        with self.portLock:
            while length > len(self._internalBuffer):
                maxPacket = inputEndPoint.wMaxPacketSize
                data = array.array('B',[0]*maxPacket)
                nBytesRead = inputEndPoint.read(size_or_buffer=data)
                self._internalBuffer += bytearray(data[:nBytesRead])

            data = self._internalBuffer[:length]
            self._internalBuffer = self._internalBuffer[length:]

        return data

    def writeData(self, data, endPoint=None) -> int:
        if not self.isOpen:
            self.open()

        if endPoint is None:
            outputEndPoint = self.defaultOutputEndPoint
        else:
            outputEndPoint = self.interface[endPoint]

        with self.portLock:
            nBytesWritten = outputEndPoint.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")

        return nBytesWritten

    def readString(self, endPoint=None) -> str:      
        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        else:
            inputEndPoint = self.interface[endPoint]

        data = bytearray()
        while True:
            try:
                data += self.readData(length=1, endPoint=endPoint)
                if data[-1] == 10: # How to write?
                    return data.decode(encoding='utf-8')
            except:
                raise IOError("Unable to read string terminator: {0}".format(data.decode(encoding='utf-8')))
