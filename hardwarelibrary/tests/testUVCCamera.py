import env
import unittest
import enum
import usb.core
import usb.util
import struct
from typing import NamedTuple

class DeviceDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bcdUSB : int
    bDeviceClass : int
    bDeviceSubClass : int
    bDeviceProtocol : int
    bMaxPacketSize0 : int
    idVendor : int
    idproduct : int
    bcdDevice : int
    iManufacturer : int
    iProduct : int
    iSerialNumber : int
    bNumConfigurations : int
    packingFormat = "<BBHBBBBHHHBBBB"

class ConfigurationDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    wTotalLength : int
    bNumInterfaces : int
    bConfigurationValue : int
    iConfiguration : int
    bmAttributes : int
    bMaxPower : int
    packingFormat = "<BBHBBBBB"

class InterfaceDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bInterfaceNumber : int
    bAlternateSetting : int
    bNumEndpoints : int
    bInterfaceClass : int
    bInterfaceSubClass : int
    bInterfaceProtocol : int
    iInterface : int
    packingFormat = "<BBBBBBBBB"

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

        theStruct = struct.unpack(DeviceDescriptor.packingFormat, ret)
        desc = DeviceDescriptor(*theStruct)
        print(desc)

    def testGetConfigurationDescriptor(self):
        device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)

        ret = device.ctrl_transfer(usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE,
                      bRequest=Request.GET_DESCRIPTOR,
                      wValue=(usb.util.DESC_TYPE_CONFIG << 8),
                      wIndex=0,
                      data_or_wLength=0x09)
        # print(ret)
        self.assertTrue(len(ret) >= 2)

        theStruct = struct.unpack(ConfigurationDescriptor.packingFormat, ret)
        desc = ConfigurationDescriptor(*theStruct)

        wTotalLength = ret[2] | (ret[3]<<8)
        self.assertEqual(desc.wTotalLength, wTotalLength)

        ret = device.ctrl_transfer(usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE,
                      bRequest=Request.GET_DESCRIPTOR,
                      wValue=(usb.util.DESC_TYPE_CONFIG << 8),
                      wIndex=0,
                      data_or_wLength=wTotalLength)
        print(ret)

    @unittest.skip("testGetInterfaceDescriptor: This is not possible: we must use the full configuration request")
    def testGetInterfaceDescriptor(self):
        """
        Set Descriptor/Get Descriptor is used to return the specified descriptor in wValue. A request for the configuration descriptor will return the device descriptor and all interface and endpoint descriptors in the one request.

        Endpoint Descriptors cannot be accessed directly by a GetDescriptor/SetDescriptor Request.
        Interface Descriptors cannot be accessed directly by a GetDescriptor/SetDescriptor Request.
        String Descriptors include a Language ID in wIndex to allow for multiple language support.
        """
        device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)

        ret = device.ctrl_transfer(usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE,
                      bRequest=Request.GET_DESCRIPTOR,
                      wValue=(usb.util.DESC_TYPE_INTERFACE << 8),
                      wIndex=0,
                      data_or_wLength=0x09)

        self.assertTrue(len(ret) >= 2)
        print(ret)
        theStruct = struct.unpack(InterfaceDescriptor.packingFormat, ret)
        desc = InterfaceDescriptor(*theStruct)
        print(desc)
if __name__ == '__main__':
    unittest.main()
