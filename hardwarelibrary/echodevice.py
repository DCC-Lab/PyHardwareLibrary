from hardwarelibrary.physicaldevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.serialport import *
from hardwarelibrary.communication.commands import DataCommand, DataDecoder, TextCommand
from hardwarelibrary.communication.debugport import TableDrivenDebugPort

import re
import time
from struct import *

from pyftdi.ftdi import Ftdi #FIXME: should not be here.


class EchoDevice(PhysicalDevice):
    classIdProduct = 0x6001
    classIdVendor = 0x0403
    commands = {
        "ECHO1": TextCommand(name="ECHO1", requestEncoder="someText", replyDecoder="someText"),
        "ECHO2": TextCommand(name="ECHO2", requestEncoder="someOtherText", replyDecoder="someOtherText"),
        "ECHO3": DataCommand(name="ECHO3", data=b"someData",
                             replyDecoder=DataDecoder(length=len(b"someData"))),
    }

    def __init__(self, serialNumber='ftDXIKC4', idProduct=classIdProduct, idVendor=classIdVendor):
        PhysicalDevice.__init__(self, serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)

    def doInitializeDevice(self):
        if self.serialNumber == "debug":
            self.port = self.DebugSerialPort()
        else:
            self.port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct)
        self.port.open()

    def doShutdownDevice(self):
        self.port.close()

    class DebugSerialPort(TableDrivenDebugPort):
        def __init__(self):
            super().__init__(commands=EchoDevice.commands)

        def process_command(self, name, params, endPointIndex):
            if name == 'ECHO1':
                return 'someText'
            elif name == 'ECHO2':
                return 'someOtherText'
            elif name == 'ECHO3':
                return b'someData'
