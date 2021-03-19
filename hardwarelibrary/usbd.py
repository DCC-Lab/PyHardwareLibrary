import usb.core
import usb.util
from usbport import *
from os import listdir
from os.path import isfile, join
import re
from typing import NamedTuple

class USBParameters(NamedTuple):
    configuration : int = None
    interface: int = 0
    alternate: int = 0
    outputEndpoint : int = None
    inputEndpoint : int = None    
    
class USBDeviceDescription:
    def __init__(self, name, idVendor=None, idProduct=None, isSerializable=False):
        self.name = name
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.isSerializable = isSerializable
        self.serialPort = None
        self.regexPOSIXPort = "Nothing"

        self.usbPort = None
        self.usbParameters = None

    @property
    def isVisible(self):
        return self.isVisibleOnUSBHub or self.isVisibleAsPOSIXPort

    @property
    def isVisibleOnUSBHub(self):
        dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        isVisible = dev is not None
        usb.util.dispose_resources(dev)
        return isVisible

    @property
    def isVisibleAsPOSIXPort(self):
        if len(self.bsdPathMatches) == 1:
            return True

        return False

    @property
    def hasUniquePOSIXPortMatch(self):
        return len(self.bsdPathMatches) == 1

    @property
    def bsdPath(self):
        if self.hasUniquePOSIXPortMatch:
            return "/dev/{0}".format(self.bsdPathMatches[0])
        return None

    @property
    def bsdPathMatches(self):
        prog = re.compile(self.regexPOSIXPort)
        
        matches = []
        for path in listdir("/dev"):
            if prog.match(path):
                matches.append(path)

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
    def posixPortCanBeOpened(self):
        if self.hasUniquePOSIXPortMatch:
            port = SerialPort(bsdPath=self.bsdPath)
        else:
            return False
        isOpen = False
        try:
            port.open()
            isOpen = port.isOpen
            port.close()
        except Exception as err:
            isOpen = False
        return isOpen

    def assertEqual(self, property, expectation):
        try:
            value = getattr(self, property)
            if value == expectation:
                print("✅ {0} == {1}".format(property, expectation))
            else:
                print("🚫 {0} != {1}".format(property, expectation))

        except Exception as err:
            print("🚫 {0} failed. Exception {1}".format(property, err))


    def assertNotEqual(self, property, expectation):
        try:
            value = getattr(self, property)
            if value != expectation:
                print("✅ {0} != {1}".format(property, expectation))
            else:
                print("🚫 {0} == {1}".format(property, expectation))

        except Exception as err:
            print("🚫 {0} failed. Exception {1}".format(property, err))

    def report(self):
        print("Diagnostic report for device {0} [vid{1} pid{2}]".format(self.name, self.idVendor, self.idProduct))
        self.assertEqual('isVisible', True)
        self.assertEqual('isVisibleOnUSBHub', True)
        self.assertEqual('isVisibleAsPOSIXPort', True)
        self.assertEqual('posixPortCanBeOpened', True)
        self.assertEqual('hasUniquePOSIXPortMatch', True)
        self.assertEqual('usbPortCanBeOpened', True)


if __name__ == '__main__':
    dev = USBDeviceDescription("Optotune lens", idVendor=0x03eb, idProduct=0x2018)
    dev.regexPOSIXPort = r"cu.usbmodem\d{6}"
    dev.usbParameters = USBParameters(configuration=0, 
                                      interface=1,
                                      outputEndpoint=0,
                                      inputEndpoint=1)

    dev.report()

