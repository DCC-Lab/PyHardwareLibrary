from hardwarelibrary.physicaldevice import *
from hardwarelibrary.motion.linearmotiondevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.usbport import USBPort
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.commands import DataCommand
from hardwarelibrary.communication.debugport import TableDrivenDebugPort

import re
import time
from struct import *

from pyftdi.ftdi import Ftdi #FIXME: should not be here.

class SutterDevice(LinearMotionDevice):
    classIdVendor = 4930
    classIdProduct = 1

    commands = {
        "MOVE": DataCommand(name="MOVE", prefix=b'M',
                            sendFormat='<clllc',
                            sendFields=('header', 'x', 'y', 'z', 'terminator'),
                            sendDefaults={'header': b'M', 'terminator': b'\r'},
                            requestFormat='<xlllx', requestFields=('x', 'y', 'z'),
                            replyDataLength=1, unpackingMask='<c'),
        "GET_POSITION": DataCommand(name="GET_POSITION", prefix=b'C',
                                    data=pack('<cc', b'C', b'\r'),
                                    replyDataLength=14, unpackingMask='<xlllx',
                                    responseFormat='<clllc',
                                    responseFields=('header', 'x', 'y', 'z', 'terminator')),
        "HOME": DataCommand(name="HOME", prefix=b'H',
                            data=pack('<cc', b'H', b'\r'),
                            replyDataLength=1, unpackingMask='<c'),
        "WORK": DataCommand(name="WORK", prefix=b'Y',
                            data=pack('<cc', b'Y', b'\r'),
                            replyDataLength=1, unpackingMask='<c'),
    }

    def __init__(self, serialNumber: str = None):
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor, idProduct=self.classIdProduct)
        self.port = None
        self.nativeStepsPerMicrons = 16

        # All values are in native units (i.e. microsteps)
        self.xMinLimit = 0
        self.yMinLimit = 0
        self.zMinLimit = 0
        self.xMaxLimit = 25000*16
        self.yMaxLimit = 25000*16
        self.zMaxLimit = 25000*16

    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def doInitializeDevice(self): 
        try:
            if self.serialNumber == "debug":
                self.port = self.DebugSerialPort()
            else:
                portPath = SerialPort.matchAnyPort(idVendor=self.idVendor, idProduct=self.idProduct, serialNumber=self.serialNumber)
                if portPath is None:
                    raise PhysicalDevice.UnableToInitialize("No Sutter Device connected")

                self.port = SerialPort(portPath=portPath)
                self.port.open(baudRate=128000, timeout=10)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port for serial '{0}'".format(self.serialNumber))

            self.positionInMicrosteps()

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDevice.UnableToInitialize(error)

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def sendCommandBytes(self, commandBytes):
        """ The function to write a command to the endpoint. It will initialize the device 
        if it is not alread initialized. On failure, it will warn and shutdown."""
        if self.port is None:
            self.initializeDevice()
        
        time.sleep(0.1)
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

        time.sleep(0.1)
        replyBytes = self.port.readData(size)
        if len(replyBytes) != size:
            raise Exception(f"Not enough bytes read in readReply {replyBytes}")

        # print(replyBytes, format)
        # print(unpack(format, replyBytes))
        return unpack(format, replyBytes)

    def sendCommand(self, name, **params):
        """Send a command from the commands dict and return the unpacked reply."""
        cmd = self.commands[name]
        data = cmd.buildSendData(**params)
        self.sendCommandBytes(data)
        if cmd.replyDataLength > 0:
            return self.readReply(cmd.replyDataLength, cmd.unpackingMask)
        return None

    def positionInMicrosteps(self) -> (int, int, int):  # for compatibility
        return self.doGetPosition()

    def doGetPosition(self) -> (int, int, int):
        """ Returns the position in microsteps """
        (x, y, z) = self.sendCommand("GET_POSITION")
        return (x, y, z)

    def doMoveTo(self, position):
        """ Move to a position in microsteps """
        x, y, z = position
        reply = self.sendCommand("MOVE", x=int(x), y=int(y), z=int(z))
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
        reply = self.sendCommand("HOME")
        if reply != (b'\r',):
            raise Exception(f"Expected carriage return, but got {reply} instead.")

    def work(self):
        self.home()
        reply = self.sendCommand("WORK")
        if reply != (b'\r',):
            raise Exception(f"Expected carriage return, but got {reply} instead.")


    class DebugSerialPort(TableDrivenDebugPort):
        def __init__(self):
            super().__init__(commands=SutterDevice.commands)
            self.xSteps = 0
            self.ySteps = 0
            self.zSteps = 0

        def process_command(self, name, params, endPointIndex):
            if name == 'MOVE':
                self.xSteps = params['x']
                self.ySteps = params['y']
                self.zSteps = params['z']
                return b'\r'
            elif name == 'GET_POSITION':
                return {'header': b'c', 'x': self.xSteps,
                        'y': self.ySteps, 'z': self.zSteps,
                        'terminator': b'\r'}
            elif name == 'HOME':
                self.xSteps = self.ySteps = self.zSteps = 0
                return b'\r'
            elif name == 'WORK':
                return b'\r'
