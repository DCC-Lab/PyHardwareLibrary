import usb.core
import usb.util
from usbport import *
from os import listdir, stat, system
from stat import *
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
        self.mustAssertTrue = []
        self.mustAssertFalse = []
        self.catchExceptions = False
        
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

    def diagnoseConnectivity(self):
        import subprocess
        isPhysicallyConnectedAndTurnedOn = []
        try:
            try:
                response = self.isVisibleOnUSBHub
            except:
                response = False
            isPhysicallyConnectedAndTurnedOn.append(response)

            response = subprocess.check_output(['ioreg', '-n"{0}"'.format(self.name), '-r'])
            if len(response) == 0:
                print("⚠️  Using ioreg, the device does not appear connected under the name '{0}'".format(self.name))
                isPhysicallyConnectedAndTurnedOn.append(False)

            if self.hasUniquePOSIXPortMatch:
                print("❓  This is surprising, because it appears visible in {0}".format(self.bsdPath))
                print("❓  The name used for matching in ioreg may be wrongly configured: {0}".format(self.name))                    
                isPhysicallyConnectedAndTurnedOn = None
            elif len(self.bsdPathMatches) > 1:
                print("⚠️  Unable to find a unique matching port in /dev/: {0}".format(self.bsdPathMatches))
                print("    It appears more than 1 devices match the POSIX path-regex '{0}'".format(self.regexPOSIXPort))
                isPhysicallyConnectedAndTurnedOn = None
            elif len(self.bsdPathMatches) == 0:
                isPhysicallyConnectedAndTurnedOn = False
                print("‼️  After other checks (/dev/ and ioreg): the device is not physically connected or off")
            else:
                isPhysicallyConnectedAndTurnedOn = True
        except Exception as err:
            print("Unable to complete connectivity diagnosis : {0}".format(err))

    @property
    def isVisibleAsPOSIXPort(self):
        if self.hasUniquePOSIXPortMatch:
            return True
        else:
            raise RuntimeError("POSIX path does not exist: {0}".format(self.bsdPath))
        return False

    @property
    def isValidPOSIXPath(self):
        if not exists(self.bsdPath):
            raise RuntimeError("POSIX path does not exist: {0}".format(self.bsdPath))

        mode = stat(self.bsdPath).st_mode
        if not S_ISCHR(mode):
            raise RuntimeError("POSIX path is not a character device: {0}".format(self.bsdPath))            
        
        return True
    
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
                if dev is None:
                    raise RuntimeError("Cannot find device with usb.core")

                dev.set_configuration()
                conf = dev.get_active_configuration()
                if conf is None:
                    raise RuntimeError("Cannot configure device")
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
                    replyData = self.posixPort.readData(length=len(command.replyData))
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
        for property in self.mustAssertTrue:
            self.assertTrue(property)

if __name__ == '__main__':
    dev = USBDeviceDescription("Optotune LD", idVendor=0x03eb, idProduct=0x2018)
    dev.regexPOSIXPort = r"cu.usbmodem\d{6}"
    dev.usbParameters = USBParameters(configuration=0, 
                                      interface=1,
                                      alternate=0,
                                      outputEndpoint=0,
                                      inputEndpoint=1)
    dev.mustAssertTrue = ['isVisible', 'isVisibleOnUSBHub','isVisibleAsPOSIXPort',
                          'isValidPOSIXPath','posixPortCanBeOpened', 'hasUniquePOSIXPortMatch', 
                          'usbPortCanBeOpened', 'canReadWritePOSIXCommands',
                          'canReadWriteUSBCommands']
    dev.mustAssertFalse = []
    
    dev.deviceCommands.append(DeviceCommand(text='Start',reply='Ready\r\n'))
    dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd'))
#    dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd', replyData='\x00'))

    #dev.usbPort.open()
    # print(dev.__dict__)
    dev.diagnoseConnectivity()
#    dev.report()

