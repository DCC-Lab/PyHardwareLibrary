import usb.core
import usb.util
from usbport import *
from os import listdir, stat
from os.path import isfile, join, exists, isfile
import re
from typing import NamedTuple

class USBParameters(NamedTuple):
    configuration : int = None
    interface: int = 0
    alternate: int = 0
    outputEndpoint : int = None
    inputEndpoint : int = None    

class DeviceCommand(NamedTuple):
    text : str = None
    data : bytearray = None
    reply: str = None
    replyData: bytearray = None
    
class USBDeviceDescription:
    def __init__(self, name, idVendor=None, idProduct=None):
        self.name = name
        self.idVendor = idVendor
        self.idProduct = idProduct

        self._serialPort = None
        self.regexPOSIXPort = "Nothing"

        self._usbPort = None
        self.usbParameters = None
        self.deviceCommands = []

    @property
    def isVisible(self):
        return self.isVisibleOnUSBHub or self.isVisibleAsPOSIXPort

    @property
    def isVisibleOnUSBHub(self):
        dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if dev is None:
            raise RuntimeError("Device not visible on USB")

        isVisible = dev is not None
        usb.util.dispose_resources(dev)
        return isVisible

    @property
    def isVisibleAsPOSIXPort(self):
        if self.hasUniquePOSIXPortMatch:
            if not exists(self.bsdPath):
                raise RuntimeError("POSIX path does not exist: {0}".format(self.bsdPath))
            stat(self.bsdPath)
            return True
        else:
            raise RuntimeError("POSIX path does not exist: {0}".format(self.bsdPath))
        return False

    @property
    def isVisibleAsPOSIXPort(self):
        if self.hasUniquePOSIXPortMatch:
            if not exists(self.bsdPath):
                raise RuntimeError("POSIX path does not exist: {0}".format(self.bsdPath))
            permissions = stat(self.bsdPath)
            return True
        else:
            raise RuntimeError("POSIX path does not exist: {0}".format(self.bsdPath))
        return False

    @property
    def hasUniquePOSIXPortMatch(self):
        return len(self.bsdPathMatches) == 1

    @property
    def bsdPath(self):
        if self.hasUniquePOSIXPortMatch:
            return self.bsdPathMatches[0]
        return None

    @property
    def bsdPathMatches(self):
        prog = re.compile(self.regexPOSIXPort)
        
        matches = []
        for path in listdir("/dev"):
            if prog.match(path):
                matches.append("/dev/{0}".format(path))

        return matches

    @property
    def portCanBeOpened(self):
        return self.usbPortCanBeOpened or self.posixPortCanBeOpened
    
    @property
    def usbPortCanBeOpened(self):
        if self.usbParameters is not None:
            dev = None
            intf = None
            try:
                dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
                dev.set_configuration()
                conf = dev.get_active_configuration()
                intf = conf[(self.usbParameters.interface,self.usbParameters.alternate)]
                outputEndpoint = intf[self.usbParameters.outputEndpoint]            
                inputEndpoint = intf[self.usbParameters.inputEndpoint]
                return True
            except Exception as err:
                raise err
            finally:
                if dev is not None:
                    if intf is not None:
                        usb.util.release_interface(dev, intf)
                    usb.util.dispose_resources(dev)

        return False

    @property
    def usbPort(self):
        if not self.hasUniquePOSIXPortMatch:
            return None
        
        if self._serialPort is None:
            self._serialPort = SerialPort(bsdPath=self.bsdPath)

        return self._serialPort
 
    @property
    def posixPort(self):
        if not self.hasUniquePOSIXPortMatch:
            return None
        
        if self._serialPort is None:
            self._serialPort = SerialPort(bsdPath=self.bsdPath)

        return self._serialPort
    
    @property
    def posixPortCanBeOpened(self):
        if self.posixPort is None:
            return False

        isOpen = False
        try:
            self.posixPort.open()
            isOpen = self.posixPort.isOpen
        except Exception as err:
            raise err
        finally:
            self.posixPort.close()

        return isOpen

    @property
    def canReadWritePOSIXCommands(self):
        self.posixPort.open()
        self.posixPort.flush()

        try:
            for command in self.deviceCommands:
                if command.text is not None:
                    bytesWritten = self.posixPort.writeString(command.text)
                    if bytesWritten != len(command.text):
                        return False
                elif command.data is not None:
                    bytesWritten = self.posixPort.writeData(command.data)
                    if bytesWritten != len(command.data):
                        return False

                if command.reply is not None:
                    reply = self.posixPort.readString()
                    if reply != command.reply:
                        return False
                elif command.replyData is not None:
                    replyData = self.posixPort.readData()
                    if replyData != command.replyData:
                        return False

        except Exception as err:
            raise err
        finally:
            self.posixPort.close()

        return True

    @property
    def canReadWriteUSBCommands(self):
        port = USBPort(idVendor=self.idVendor, idProduct=self.idProduct, interfaceNumber=1)
        assert(port is not None)

        success = True
        try:
            for command in self.deviceCommands:
                if command.text is not None:
                    bytesWritten = port.writeString(command.text)
                    if bytesWritten != len(command.text):
                        success = False
                elif command.data is not None:
                    bytesWritten = port.writeData(command.data)
                    if bytesWritten != len(command.data):
                        success = False

                if command.reply is not None:
                    reply = port.readString()
                    if reply != command.reply:
                        success = False
                elif command.replyData is not None:
                    replyData = port.readData(length=len(command.replyData))
                    if replyData != command.replyData:
                        success = False

        except Exception as err:
            raise err

        return success

    def assertTrue(self, property):
        try:
            value = getattr(self, property)
            if value:
                print("✅ {0}".format(property))
            else:
                print("🚫 !{0}".format(property))
        except Exception as err:
            print("🚫 {0} failed: {1}".format(property, err))

    def assertEqual(self, property, expectation):
        try:
            value = getattr(self, property)
            if value == expectation:
                print("✅ {0} == {1}".format(property, expectation))
            else:
                print("🚫 {0} != {1}".format(property, expectation))
        except Exception as err:
            print("🚫 {0} failed: {1}".format(property, err))


    def assertNotEqual(self, property, expectation):
        try:
            value = getattr(self, property)
            if value != expectation:
                print("✅ {0} != {1}".format(property, expectation))
            else:
                print("🚫 {0} == {1}".format(property, expectation))
        except Exception as err:
            print("🚫 {0} failed: {1}".format(property, err))

    def report(self):
        print("============================================================")
        print("Diagnostic report for device {0} [vid 0x{1:04x} pid 0x{2:04x}]".format(self.name, self.idVendor, self.idProduct))
        print("============================================================")
        for key, value in self.__dict__.items():
            if key[0] == "_":
                continue # private
            print("{0} = {1}".format(key, value))

        print("------------------------------------------------------------")
        self.assertTrue('isVisible')
        self.assertTrue('isVisibleOnUSBHub')
        self.assertTrue('isVisibleAsPOSIXPort')
        self.assertTrue('posixPortCanBeOpened')
        self.assertTrue('hasUniquePOSIXPortMatch')
        self.assertTrue('usbPortCanBeOpened')
        self.assertTrue('canReadWritePOSIXCommands')
        self.assertTrue('canReadWriteUSBCommands')


if __name__ == '__main__':
    dev = USBDeviceDescription("Optotune lens", idVendor=0x03eb, idProduct=0x2018)
    dev.regexPOSIXPort = r"cu.usbmodem\d{6}"
    dev.usbParameters = USBParameters(configuration=0, 
                                      interface=1,
                                      alternate=0,
                                      outputEndpoint=0,
                                      inputEndpoint=1)
    
    dev.deviceCommands.append(DeviceCommand(text='Start',reply='Ready\r\n'))
    dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd'))
    dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd'))
    #dev.usbPort.open()
    dev.report()

