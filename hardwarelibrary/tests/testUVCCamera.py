import env
import unittest
import enum
import usb.core
import usb.util

# """
# USB information available at https://www.beyondlogic.org/usbnutshell/usb6.shtml
# """
#
class RequestType(enum.IntEnum):
    outVendorDevice = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    inVendorDevice = usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
#
# """
# Vendor-specific request for StellarNet and EZUSB, as accepted by the USB
# standard and defined in the firmware for EZUSB.
# """
#
class Request(enum.IntEnum):
    GET_STATUS = 0x00
    CLEAR_FEATURE = 0x01
    SET_FEATURE = 0x03
    SET_ADDRESS = 0x05
    GET_DESCRIPTOR = 0x06
    SET_DESCRIPTOR = 0x07
    GET_CONFIGURATION = 0x08
    SET_CONFIGURATION = 0x09
#
# """
# Memory address for Reset on EZUSB chip
# """
#
# class Value(enum.IntEnum):
#     reset = 0xE600
#
# """
# Reset ON/OFF values
# """
#
# class Data(enum.IntEnum):
#     resetON = 1
#     resetOFF = 0

class TestUVCCamera(unittest.TestCase):
    def testUSBDevices(self):
        devices = list(usb.core.find(find_all=True))
        self.assertIsNotNone(devices)
        self.assertTrue(len(devices) > 0)

    def testGetFacetimeCam(self):
        devices = list(usb.core.find(idVendor=0x05ac, idProduct=0x1112))
        self.assertIsNotNone(devices)
        self.assertTrue(len(devices) == 1)
        cam = devices[0]

    def testGetClassFromConfig(self):
        device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)
        conf = device.get_active_configuration()
        self.assertIsNotNone(conf)

        with self.assertRaises(Exception):
            conf.bDeviceClass

    def testGetClassFromInterface(self):
        device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)
        conf = device.get_active_configuration()

        uvcInterfaces = 0
        for itf in conf:
            if itf.bInterfaceClass == 0xe:
                uvcInterfaces += 1

        self.assertTrue(uvcInterfaces > 0)

    def testSendStatusControlRequest(self):
        device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)

        ret = device.ctrl_transfer(usb.util.CTRL_IN,
                      bRequest=Request.GET_STATUS,
                      wValue=0,
                      wIndex=0,
                      data_or_wLength=2)
        self.assertEqual(ret[0] | (ret[1] << 8), 0)

    def testGetDeviceDescriptor(self):
        device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)

        ret = device.ctrl_transfer(usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE,
                      bRequest=Request.GET_DESCRIPTOR,
                      wValue=(usb.util.DESC_TYPE_DEVICE << 8) ,
                      wIndex=0,
                      data_or_wLength=0x12)
        print(ret)

    def testGetConfigurationDescriptor(self):
        device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)

        ret = device.ctrl_transfer(usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE,
                      bRequest=Request.GET_DESCRIPTOR,
                      wValue=(usb.util.DESC_TYPE_CONFIG << 8),
                      wIndex=0,
                      data_or_wLength=0x09)
        # print(ret)
        self.assertTrue(len(ret) >= 2)

        wTotalLength = ret[2] | (ret[3]<<8)
        print(wTotalLength)
        ret = device.ctrl_transfer(usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE,
                      bRequest=Request.GET_DESCRIPTOR,
                      wValue=(usb.util.DESC_TYPE_CONFIG << 8),
                      wIndex=0,
                      data_or_wLength=wTotalLength)
        print(ret)

if __name__ == '__main__':
    unittest.main()
