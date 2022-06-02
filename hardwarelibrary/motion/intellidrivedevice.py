from hardwarelibrary.physicaldevice import *
from hardwarelibrary.motion.rotationmotiondevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.usbport import USBPort
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.commands import DataCommand
from hardwarelibrary.communication.debugport import DebugPort

import re
import time
from struct import *

from pyftdi.ftdi import Ftdi #FIXME: should not be here.

class State(Enum):
    notInit = 0,
    init = 1,
    unknown = 2,
    referenced = 3,
    configuration = 4,
    homing = 5,
    moving = 6,
    ready = 7,
    disable = 8,
    jogging = 9


class IntellidriveDevice(RotationDevice):
    classIdVendor = 4930
    classIdProduct = 1

    def __init__(self):
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor, idProduct=self.classIdProduct)
        self.orientation = None
        self.internalState = State.notInit
        self.stepsPerDegree = 138.888;

    def doGetOrientation(self) -> float:
        return self._debugOrientation

    def doMoveTo(self, angle):
        self._debugOrientation = angle

    def doMoveBy(self, displacement):
        self._debugOrientation += angle

    def doHome(self):
        self._debugOrientation = 0

    def doInitializeDevice(self): 
        try:
            if self.serialNumber == "debug":
                self.port = self.DebugSerialPort()
            else:
                portPath = SerialPort.matchAnyPort(idVendor=self.idVendor, idProduct=self.idProduct, serialNumber=self.serialNumber)
                if portPath is None:
                    raise PhysicalDevice.UnableToInitialize("No Intellidrive Device connected")

                self.port = SerialPort(portPath=portPath)
                self.port.open(baudRate=9600, bits=8, parity = None, stop=1, timeout=10)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port {0}".format(portPath))

            self.serialPort.writeString("s r0x24 31\r", expectStringMatching:"ok\r")
            self.serialPort.writeString("s r0xc2 514\r", expectStringMatching:"ok\r")


        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDevice.UnableToInitialize(error)

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def doGetPosition(self) -> (int, int, int):
        """ Returns the position in microsteps """
        commandBytes = pack('<cc', b'C', b'\r')
        self.sendCommandBytes(commandBytes)
        (x, y, z) = self.readReply(size=14, format='<xlllx')

        return (x, y, z)

    def doMoveTo(self, position):
        """ Move to a position in microsteps """
        x, y, z = position
        commandBytes = pack('<clllc', b'M', int(x), int(y), int(z), b'\r')
        self.sendCommandBytes(commandBytes)
        reply = self.readReply(size=1, format='<c')

        if reply != (b'\r',):
            raise Exception(f"Expected carriage return, but got '{reply}' instead.")

    def doMoveBy(self, displacement):
        dx, dy, dz = displacement
        x, y, z = self.doGetPosition()
        if x is not None:
            self.doMoveTo((x+dx, y+dy, z+dz))
        else:
            raise Exception("Unable to read position from device")

    def doHome(self):
        commandBytes = pack('<cc', b'H', b'\r')
        self.sendCommandBytes(commandBytes)
        replyBytes = self.readReply(1, '<c')
        if replyBytes is None:
            raise Exception(f"Nothing received in respnse to {commandBytes}")
        if replyBytes != (b'\r',):
            raise Exception(f"Expected carriage return, but got {replyBytes} instead.")     
        