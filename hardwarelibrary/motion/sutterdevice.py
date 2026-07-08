from hardwarelibrary.physicaldevice import *
from hardwarelibrary.motion.linearmotiondevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.usbport import USBPort
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.commands import DataCommand, DataEncoder, DataDecoder
from hardwarelibrary.communication.debugport import TableDrivenDebugPort

import re
import time
from struct import *

class SutterDevice(LinearMotionDevice):
    classIdVendor = 4930
    classIdProduct = 1

    commands = {
        "MOVE": DataCommand(name="MOVE",
            requestEncoder=DataEncoder('<clllc',
                                       ('header', 'x', 'y', 'z', 'terminator'),
                                       {'header': b'M', 'terminator': b'\r'}),
            requestDecoder=DataDecoder('<xlllx', ('x', 'y', 'z'), prefix=b'M'),
            replyDecoder=DataDecoder('<c', length=1),
        ),
        "GET_POSITION": DataCommand(name="GET_POSITION",
            data=pack('<cc', b'C', b'\r'),
            replyDecoder=DataDecoder('<lllx', length=13),
            replyEncoder=DataEncoder('<lllc', ('x', 'y', 'z', 'terminator')),
        ),
        "HOME": DataCommand(name="HOME",
            data=pack('<cc', b'H', b'\r'),
            replyDecoder=DataDecoder('<c', length=1),
        ),
        "WORK": DataCommand(name="WORK",
            data=pack('<cc', b'Y', b'\r'),
            replyDecoder=DataDecoder('<c', length=1),
        ),
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

                self.port = SerialPort(portPath=portPath, delay=0.1)
                self.port.open(baudRate=128000, timeout=10)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port for serial '{0}'".format(self.serialNumber))

            # Verify the device is talking. Direct .send() bypasses sendCommand's
            # state check, which would reject because state is not yet Ready here.
            self.commands["GET_POSITION"].send(port=self.port)

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            raise PhysicalDevice.UnableToInitialize(error)

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def positionInMicrosteps(self) -> (int, int, int):  # for compatibility
        return self.doGetPosition()

    def doGetPosition(self) -> (int, int, int):
        """ Returns the position in microsteps """
        cmd = self.sendCommand("GET_POSITION")
        (x, y, z) = cmd.matchGroups
        return (x, y, z)

    def doMoveTo(self, position):
        """ Move to a position in microsteps """
        x, y, z = position
        cmd = self.sendCommand("MOVE", x=int(x), y=int(y), z=int(z))
        if cmd.matchGroups != (b'\r',):
            raise Exception(f"Expected carriage return, but got '{cmd.matchGroups}' instead.")

    def doMoveBy(self, displacement):
        dx, dy, dz = displacement
        x, y, z = self.doGetPosition()
        if x is not None:
            self.doMoveTo((x+dx, y+dy, z+dz))
        else:
            raise Exception("Unable to read position from device")

    def doHome(self):
        cmd = self.sendCommand("HOME")
        if cmd.matchGroups != (b'\r',):
            raise Exception(f"Expected carriage return, but got {cmd.matchGroups} instead.")

    def work(self):
        self.home()
        cmd = self.sendCommand("WORK")
        if cmd.matchGroups != (b'\r',):
            raise Exception(f"Expected carriage return, but got {cmd.matchGroups} instead.")


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
                return {'x': self.xSteps, 'y': self.ySteps, 'z': self.zSteps,
                        'terminator': b'\r'}
            elif name == 'HOME':
                self.xSteps = self.ySteps = self.zSteps = 0
                return b'\r'
            elif name == 'WORK':
                return b'\r'
