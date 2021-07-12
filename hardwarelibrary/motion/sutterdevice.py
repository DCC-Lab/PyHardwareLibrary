from hardwarelibrary.physicaldevice import *
from hardwarelibrary.motion.linearmotiondevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.usbport import USBPort
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.commands import DataCommand

import numpy as np
import re
import time
from struct import *

class SutterDevice(PhysicalDevice):

    def __init__(self, serialNumber: str = None):

        PhysicalDevice.__init__(self, serialNumber=serialNumber, vendorId=4930, productId=1)
        self.port = None
        self.xMinLimit = 0
        self.yMinLimit = 0
        self.zMinLimit = 0
        self.xMaxLimit = 25000
        self.yMaxLimit = 25000
        self.zMaxLimit = 25000
        self.microstepsPerMicrons = 16

    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def doInitializeDevice(self): 
        try:
            if self.serialNumber == "debug":
                self.port = SutterDebugSerialPort()
            else:
                self.port = SerialPort(portPath="ftdi://0x1342:0x0001:SI8YCLBE/1")
                print(self.port)
                self.port.open(baudRate=128000, timeout=10)

            if self.port is None:
                raise PhysicalDeviceUnableToInitialize("Cannot allocate port {0}".format(self.portPath))

            self.positionInMicrosteps()

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            print(error)
            raise PhysicalDeviceUnableToInitialize(error)
        except PhysicalDeviceUnableToInitialize as error:
            raise error
        

    def doShutdownDevice(self):
        self.port.close()
        self.port = None
        return

    def sendCommand(self, commandBytes):
        """ The function to write a command to the endpoint. It will initialize the device 
        if it is not alread initialized. On failure, it will warn and shutdown."""
        if self.port is None:
            self.doInitializeDevice()
        
        nBytesWritten = self.port.writeData(commandBytes)
        if nBytesWritten != len(commandBytes):
            raise Exception(f"Unable to send command {commandBytes} to device.")

    def readReply(self, size, format) -> tuple:
        """ The function to read a reply from the endpoint. It will initialize the device 
        if it is not already initialized. On failure, it will warn and shutdown. 
        It will unpack the reply into a tuple.
        """
        if format is None:
            raise Exception("You must provide a format for unpacking in readReply")

        if self.port is None:
            self.initializeDevice()

        replyBytes = self.port.readData(size)
        if len(replyBytes) != size:
            raise Exception(f"Not enough bytes read in readReply {replyBytes}")

        # print(replyBytes, format)
        # print(unpack(format, replyBytes))
        return unpack(format, replyBytes)

    def positionInMicrosteps(self) -> (int,int,int):
        """ Returns the position in microsteps """
        commandBytes = pack('<cc', b'C', b'\r')
        self.sendCommand(commandBytes)
        (x, y, z) = self.readReply(size=14, format='<xlllx')

        return (x, y, z)

    def moveInMicrostepsTo(self, position):
        """ Move to a position in microsteps """
        x, y, z = position
        commandBytes = pack('<clllc', b'M', int(x), int(y), int(z), b'\r')
        self.sendCommand(commandBytes)
        reply = self.readReply(size=1, format='<c')

        if reply != (b'\r',):
            raise Exception(f"Expected carriage return, but got '{reply}' instead.")

    def position(self) -> (float, float, float):
        """ Returns the position in microns """

        position = self.positionInMicrosteps()
        if position is not None:
            return (position[0]/self.microstepsPerMicrons,
                    position[1]/self.microstepsPerMicrons,
                    position[2]/self.microstepsPerMicrons)
        else:
            print('whaaaaaaat')
            return (None, None, None)

    def moveTo(self, position):
        """ Move to a position in microns """
        x, y, z  = position
        positionInMicrosteps = (x*self.microstepsPerMicrons, 
                                y*self.microstepsPerMicrons,
                                z*self.microstepsPerMicrons)
        self.moveInMicrostepsTo(positionInMicrosteps)

    def moveBy(self, delta) -> bool:
        #Move by a delta displacement (dx, dy, dz) from current position in microns
        dx,dy,dz  = delta
        x,y,z = self.position()
        if x is not None:
            self.moveTo((x+dx, y+dy, z+dz))
        else:
            raise Exception("Unable to read position from device")

    def home(self):
        commandBytes = pack('<cc', b'H', b'\r')
        self.sendCommand(commandBytes)
        replyBytes = self.readReply(1, '<c')
        if replyBytes is None:
            raise Exception(f"Nothing received in respnse to {commandBytes}")
        if replyBytes != (b'\r',):
            raise Exception(f"Expected carriage return, but got {replyBytes} instead.")
        
        
    def work(self):
        self.home()
        commandBytes = pack('<cc', b'Y', b'\r')
        self.sendCommand(commandBytes)
        replyBytes = self.readReply(1, '<c')
        if replyBytes is None:
            raise Exception(f"Nothing received in respnse to {commandBytes}")
        if replyBytes != (b'\r',):
            raise Exception(f"Expected carriage return, but got {replyBytes} instead.")


class SutterDebugSerialPort(CommunicationPort):
    def __init__(self):
        super(SutterDebugSerialPort,self).__init__()
        self.xSteps = 0
        self.ySteps = 0
        self.zSteps = 0

        move = DataCommand(name='move', hexPattern='6d(.{8})(.{8})(.{8})')
        position = DataCommand(name='position', hexPattern='63')
        self.commands.append(move)
        self.commands.append(position)

    def processCommand(self, command, groups, inputData) -> bytearray:
        if command.name == 'move':
            self.x = unpack('<l',groups[0])[0]
            self.y = unpack('<l',groups[1])[0]
            self.z = unpack('<l',groups[2])[0]
            return b'\r'
        elif command.name == 'position':
            replyData = bytearray()
            replyData.extend(bytearray(pack("<l", self.x)))
            replyData.extend(bytearray(pack("<l", self.y)))
            replyData.extend(bytearray(pack("<l", self.z)))
            replyData.extend(b'\r')
            return replyData

"""
if __name__ == "__main__":
    device = SutterDevice()
    device.moveTo((0, 0, 10))
"""
