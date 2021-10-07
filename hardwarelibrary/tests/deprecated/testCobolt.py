import unittest

import usb.core
import usb.util

from usbport import *


class TestCobolt(unittest.TestCase):
    idVendor = 0x25dc

    def testGetAnyDevice(self):
        self.assertIsNotNone(usb.core.find())

    def testGetCoboltDevice(self):
        cobolt = usb.core.find(idVendor=self.idVendor)
        cobolt.default_timeout = 1000
        self.assertIsNotNone(cobolt)        
        usb.util.dispose_resources(cobolt)

    def testGetAndReleaseCoboltDevice(self):
        cobolt = usb.core.find(idVendor=self.idVendor)
        cobolt.default_timeout = 1000
        self.assertIsNotNone(cobolt)        
        usb.util.dispose_resources(cobolt)

    def testConfigureCobolt(self):
        cobolt = usb.core.find(idVendor=self.idVendor)
        cobolt.default_timeout = 1000
        cobolt.set_configuration()
        conf = cobolt.get_active_configuration()
        self.assertIsNotNone(conf)
        usb.util.dispose_resources(cobolt)

    def testGetInterfaceCobolt(self):
        cobolt = usb.core.find(idVendor=self.idVendor)
        cobolt.default_timeout = 1000
        cobolt.set_configuration()
        conf = cobolt.get_active_configuration()
        intf = conf[(0,0)]
        self.assertIsNotNone(intf)
        intf = conf[(1,0)]
        self.assertIsNotNone(intf)
        usb.util.dispose_resources(cobolt)

    def testGetEndPoints(self):
        cobolt = usb.core.find(idVendor=self.idVendor)
        cobolt.default_timeout = 1000
        cobolt.set_configuration()
        conf = cobolt.get_active_configuration()
        intf = conf[(1,0)]
        self.assertIsNotNone(intf)
        epOut = intf[0]
        epIn = intf[1]
        self.assertTrue(epOut.bEndpointAddress & 0x80 == 0)
        self.assertTrue(epIn.bEndpointAddress & 0x80 != 0)
        usb.util.dispose_resources(cobolt)

    def testWriteEndPoints(self):
        cobolt = usb.core.find(idVendor=self.idVendor)
        cobolt.default_timeout = 1000
        cobolt.set_configuration()
        conf = cobolt.get_active_configuration()
        intf = conf[(1,0)]
        epOut = intf[0]
        epIn = intf[1]
        
        self.assertEqual(epOut.write(b'sn?\r'),4)
        
        while True:
            try:
                bytesRead = epIn.read(size_or_buffer=32)
                if len(bytesRead) < 32:
                    break
            except:
                self.assertTrue(False)
        self.assertEqual(bytesRead[-1], 10)
        self.assertEqual(bytesRead[-2], 13)
        self.assertEqual(bytes(bytesRead[:-2]).decode(), '561006828')
        usb.util.dispose_resources(cobolt)


    def testGetPower(self):
        cobolt = usb.core.find(idVendor=self.idVendor)
        cobolt.default_timeout = 1000
        cobolt.set_configuration()
        conf = cobolt.get_active_configuration()
        intf = conf[(1,0)]
        epOut = intf[0]
        epIn = intf[1]
        
        self.assertEqual(epOut.write(b'pa?\r'),4)
        
        while True:
            try:
                bytesRead = epIn.read(size_or_buffer=32)
                if len(bytesRead) < 32:
                    break
            except:
                self.assertTrue(False)
        self.assertEqual(bytesRead[-1], 10)
        self.assertEqual(bytesRead[-2], 13)
        # print(self.asString(bytesRead))
        usb.util.dispose_resources(cobolt)

    def asString(self, bytesRead):
        return bytes(bytesRead[:-2]).decode()

    def testUSBPort(self):
        self.assertIsNotNone(USBPort(idVendor=self.idVendor, interfaceNumber=1))

    def testConnected(self):
        USBPort.allDevices()

if __name__ == '__main__':
    unittest.main()
