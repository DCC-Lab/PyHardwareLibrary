from hardwarelibrary.physicaldevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.serialport import *
from hardwarelibrary.communication.commands import DataCommand
from hardwarelibrary.communication.debugport import DebugPort

import re
import time
from struct import *

from pyftdi.ftdi import Ftdi #FIXME: should not be here.


class EchoDevice(PhysicalDevice):
    classIdProduct = 0x6001
    classIdVendor = 0x0403
    commands = {"ECHO1": TextCommand(name="ECHO1", text="someText", replyPattern="someText"),
                "ECHO2": TextCommand(name="ECHO2", text="someOtherText", replyPattern="someOtherText"),
                "ECHO3": DataCommand(name="ECHO3", data=b"someData", replyDataLength=len(b"someData"))}

    def __init__(self, serialNumber='ftDXIKC4', idProduct=classIdProduct, idVendor=classIdVendor):
        PhysicalDevice.__init__(self, serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)

    def doInitializeDevice(self):
        self.port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct)
        self.port.open()

    def doShutdownDevice(self):
        self.port.close()

class DebugEchoDevice(EchoDevice):
    classIdProduct = 0xfffa
    classIdVendor = 0xffff

    def __init__(self, serialNumber='debug', idProduct=classIdProduct, idVendor=classIdVendor):
        PhysicalDevice.__init__(self, serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)

    def doInitializeDevice(self):
        self.port = DebugPort()
        self.port.open()

    def doShutdownDevice(self):
        self.port.close()
