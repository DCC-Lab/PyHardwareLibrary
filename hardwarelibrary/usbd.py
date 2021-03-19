import usb.core
import usb.util
from usbport import *

class USBDeviceDescription:
    def __init__(self, name, idVendor=None, idProduct=None, isSerializable=False):
        self.name = name
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.isSerializable = isSerializable
        self.serialPort = None
        self.usbPort = None

    @property
    def isVisible(self):
        return self.isVisibleOnUSBHub or self.isVisibleAsPOSIXPort

    @property
    def isVisibleOnUSBHub(self):
        return False

    @property
    def isVisibleAsPOSIXPort(self):
        return False

    @property
    def portCanBeOpened(self):
        return self.usbPortCanBeOpened or self.posixPortCanBeOpened
    
    @property
    def usbPortCanBeOpened(self):
        return False

    @property
    def posixPortCanBeOpened(self):
        return False        

    def report(self):
        print("Diagnostic report for device {0}".format(self.name))
        if self.isVisible:
            print("✅ visible on USB or POSIX")
        else:
            print("🚫 not visible on USB or POSIX")
        if self.isVisibleOnUSBHub:
            print(" ✅ visible on USB HUB")
        else:
            print(" 🚫 not visible on USB HUB")
        if self.isVisibleAsPOSIXPort:
            print(" ✅ visible as POSIX device in /dev/")
        else:
            print(" 🚫 not visible as POSIX device in /dev/")

if __name__ == '__main__':
    dev = USBDeviceDescription("Optotune lens", idVendor=0x03eb, idProduct=0x2018)
    dev.report()

