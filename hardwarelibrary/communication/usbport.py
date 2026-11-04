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
        self.defaultTimeout = 500
        self._internalBuffer = bytearray()

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
        if self.isOpen:
            raise Exception("Port already open")

        self._internalBuffer = bytearray()

        if self.serialNumber is not None:
            def matchesSerial(device):
                try:
                    return device.serial_number == self.serialNumber
                except (ValueError, usb.core.USBError):
                    return False  # serial unreadable without opening: not a match
            self.device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct,
                                        custom_match=matchesSerial)
        else:
            self.device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.device is None:
            raise IOError("Can't find device")

        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(self.interfaceNumber,0)]
        
        outputIndex, inputIndex = self.defaultEndPointsIndex
        self.defaultOutputEndPoint = self.interface[outputIndex]
        if self.defaultOutputEndPoint.bEndpointAddress & 0x80 != 0:
            raise Exception("Endpoint {0} is an input, not an output".format(outputIndex))

        self.defaultInputEndPoint = self.interface[inputIndex]
        if self.defaultInputEndPoint.bEndpointAddress & 0x80 == 0:
            raise Exception("Endpoint {0} is an output, not an input".format(inputIndex))

        self.flush()

    def close(self):
        with self.portLock:
            self._internalBuffer = None
            
            if self.device is not None:
                usb.util.dispose_resources(self.device)
                self.device = None
                self.configuration = None
                self.interface = None        
                self.defaultOutputEndPoint = None
                self.defaultInputEndPoint = None

    def bytesAvailable(self, endPoint=None) -> int:
        with self.portLock:
            return len(self._internalBuffer)

    def flush(self, endPoint=None):
        self._internalBuffer = bytearray()
        if self.isNotOpen:
            return

        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        elif isinstance(endPoint, int):
            inputEndPoint = self.interface[endPoint]
        else:
            inputEndPoint = endPoint

        time.sleep(0.1)
        
        with self.portLock:            
            data = usb.util.create_buffer(inputEndPoint.wMaxPacketSize)
            try:
                nBytesRead = inputEndPoint.read(size_or_buffer=data, timeout=100)
            except:
                pass # not an error

        time.sleep(0.1)


    def readData(self, length, endPoint=None) -> bytearray:
        if not self.isOpen:
            self.open()

        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        elif isinstance(endPoint, int):
            inputEndPoint = self.interface[endPoint]
        else:
            inputEndPoint = endPoint

        with self.portLock:
            while length > len(self._internalBuffer):
                data = usb.util.create_buffer(inputEndPoint.wMaxPacketSize)
                nBytesRead = inputEndPoint.read(size_or_buffer=data, timeout=self.defaultTimeout)
                self._internalBuffer += bytearray(data[:nBytesRead])

            data = self._internalBuffer[:length]
            self._internalBuffer = self._internalBuffer[length:]

        return data

    def endPointForAddress(self, address):
        """Return the interface endpoint whose bEndpointAddress equals `address`.

        Lets a caller target an endpoint by its USB address (e.g. 0x83) rather than
        by its index in the interface, which is clearer on devices with several
        endpoints. Returns None if there is no such endpoint.
        """
        for endPoint in self.interface:
            if endPoint.bEndpointAddress == address:
                return endPoint
        return None

    def readStream(self, length, endPoint=None, chunkSize=None, timeout=None) -> bytearray:
        """Read `length` bytes from a bulk IN endpoint at full throughput.

        Unlike readData(), which reads one wMaxPacketSize packet at a time into an
        internal buffer for a command/response dialog, readStream() reads in large
        chunks in a tight loop, which sustains the endpoint's full (SuperSpeed burst)
        rate -- fast enough for an image or data stream, e.g. a multi-megapixel
        camera frame, without the device's FIFO overrunning and corrupting the data.

        `endPoint` is the default input endpoint when None, an endpoint index (int,
        as elsewhere in this class), or an endpoint object from endPointForAddress().
        `chunkSize` defaults to the endpoint's maximum burst (wMaxPacketSize * 16,
        i.e. 16 KB for a SuperSpeed bulk endpoint); the final short read trims the
        result to exactly `length`. This path does not touch the internal buffer.
        """
        if not self.isOpen:
            self.open()

        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        elif isinstance(endPoint, int):
            inputEndPoint = self.interface[endPoint]
        else:
            inputEndPoint = endPoint

        if chunkSize is None:
            chunkSize = inputEndPoint.wMaxPacketSize * 16
        if timeout is None:
            timeout = self.defaultTimeout

        data = bytearray()
        buffer = usb.util.create_buffer(chunkSize)
        with self.portLock:
            while len(data) < length:
                nBytesRead = inputEndPoint.read(size_or_buffer=buffer, timeout=timeout)
                if nBytesRead == 0:
                    break
                data += bytearray(buffer[:nBytesRead])

        return data[:length]

    def writeData(self, data, endPoint=None) -> int:
        if not self.isOpen:
            self.open()

        if endPoint is None:
            outputEndPoint = self.defaultOutputEndPoint
        elif isinstance(endPoint, int):
            outputEndPoint = self.interface[endPoint]
        else:
            outputEndPoint = endPoint

        with self.portLock:
            nBytesWritten = outputEndPoint.write(data, timeout=self.defaultTimeout)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port: actual {0} requested {1}".format(nBytesWritten, len(data)))

        return nBytesWritten

    def readString(self, endPoint=None) -> str:      
        data = bytearray()
        while True:
            try:
                data += self.readData(length=1, endPoint=endPoint)
                if data[-1] == 10: # How to write '\n' ?
                    return data.decode(encoding='utf-8')
            except Exception as err:
                raise IOError("Unable to read string terminator: {0}".format(err))
