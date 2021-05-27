import env # modifies path
import unittest
import time
import array
import os

from hardwarelibrary.communication import *

import usb.core
import usb.util

class TestUSBDevices(unittest.TestCase):
    idVendor = 0x1532
    idProduct = 0x005c

    def testList(self):
        USBPort.allDevices()

    def testDevice(self):
        dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        self.assertIsNotNone(dev)
        dev.set_configuration()
        cfg = dev.get_active_configuration()
        intf = cfg[(0,0)]
        endpoint = intf[0]
        self.assertIsNotNone(endpoint)
        try:
            usb.util.claim_interface(dev, 0)
        except usb.core.USBError as err:
            if err.errno == 13:
                print(err.errno)

if __name__ == '__main__':
    unittest.main()
