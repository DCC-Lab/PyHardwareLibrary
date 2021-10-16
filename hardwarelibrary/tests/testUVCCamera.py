import env
import unittest
import enum
import usb.core
import usb.util
import struct
from typing import NamedTuple

"""
https://www.engineersgarage.com/usb-descriptors-and-their-types-part-3-6/
"""


class DescriptorType(enum.IntEnum):
    Device = 0x01
    Configuration = 0x02
    String = 0x03
    Interface = 0x04
    Endpoint = 0x05
    Device_Qualifier = 0x06
    Other_speed_configation = 0x07
    Interface_power = 0x08
    On_the_go = 0x09
    Debug = 0x0a
    Interface_Association = 0x0b
    HID = 0x11
    CS_INTERFACE = 0x24
    CS_ENDPOINT = 0x25

class DescriptorSubType(enum.IntEnum):
    VC_HEADER = 0x01
    VC_INPUT_TERMINAL = 0x02
    VC_OUTPUT_TERMINAL = 0x03
    VC_SELECTOR_UNIT = 0x04
    VC_PROCESSING_UNIT = 0x05

class UnknownDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: DescriptorType
    bytes: bytearray = None
    packingFormat = "<BB"


class DeviceDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bcdUSB: int
    bDeviceClass: int
    bDeviceSubClass: int
    bDeviceProtocol: int
    bMaxPacketSize0: int
    idVendor: int
    idproduct: int
    bcdDevice: int
    iManufacturer: int
    iProduct: int
    iSerialNumber: int
    bNumConfigurations: int
    packingFormat = "<BBHBBBBHHHBBBB"


class ConfigurationDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    wTotalLength: int
    bNumInterfaces: int
    bConfigurationValue: int
    iConfiguration: int
    bmAttributes: int
    bMaxPower: int
    packingFormat = "<BBHBBBBB"


class InterfaceAssociationDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bFirstInterface: int
    bInterfaceCount: int
    bFunctionClass: int
    bFunctionSubClass: int
    bFunctionProtocol: int
    iFunction: int
    packingFormat = "<BBBBBBBB"


class InterfaceDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bInterfaceNumber: int
    bAlternateSetting: int
    bNumEndpoints: int
    bInterfaceClass: int
    bInterfaceSubClass: int
    bInterfaceProtocol: int
    iInterface: int
    packingFormat = "<BBBBBBBBB"

class ClassSpecificInterfaceDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    bytes: bytearray = None
    packingFormat = "<BBB"

class ClassSpecificVCHeaderInterfaceDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    bcdUVC: int
    wTotalLength: int
    dwClockFrequency: int
    bInCollection: int
    baInterfaceNr: int = 0
    packingFormat = "<BBBHHLB{0}B"


class ClassSpecificVCInputTerminalDescriptorCamera(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    bTerminalID: int
    wTerminalType: int
    bAssocTerminal: int
    iTerminal: int
    wObjectiveFocalLengthMin: int
    wObjectiveFocalLengthMax: int
    wOcularFocalLength: int
    bControlSize: int
    bmControls: int
    packingFormat = "<BBBBHBBHHHBH"


class ClassSpecificVCInputTerminalDescriptorComposite(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    bTerminalID: int
    wTerminalType: int
    bAssocTerminal: int
    iTerminal: int
    packingFormat = "<BBBBHBB"


class ClassSpecificVCOutputTerminalDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    bTerminalID: int
    wTerminalType: int
    bAssocTerminal: int
    bSourceID: int
    iTerminal: int
    packingFormat = "<BBBBHBBB"


class ClassSpecificVCSelectorUnitDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    bUnitID: int
    bNrInPins: int
    baSourceID1: int
    baSourceID2: int
    iSelector: int
    packingFormat = "<BBBBBBBB"


class ClassSpecificVCProcessingUnitDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    bUnitID: int
    bSourceID: int
    wMaxMultiplier: int
    bControlSize: int
    bmControls: int
    iProcessing: int
    bmVideoStandards: int
    packingFormat = "<BBBBBHBHBB"


class StandardInterruptEndpointDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bEndpointAddress: int
    bmAttributes: int
    wMaxPacketSize: int
    bInterval: int
    packingFormat = "<BBBBHB"


class ClassSpecificInterruptEndpointDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bDescriptorSubType: int
    wMaxTransferSize: int
    packingFormat = "<BBBH"


class EndpointDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bEndpointAddress: int
    bmAttributes: int
    wMaxPacketSize: int
    bInterval: int
    packingFormat = "<BBBBHB"


class StringDescriptor0(NamedTuple):
    bLength: int
    bDescriptorType: int
    wLANGID: list
    packingFormat = "<BB{0}H"


class StringDescriptor(NamedTuple):
    bLength: int
    bDescriptorType: int
    bString: str
    packingFormat = "<BB{0}H"


# """
# USB information available at https://www.beyondlogic.org/usbnutshell/usb6.shtml
# """
#
class RequestType(enum.IntEnum):
    outVendorDevice = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE
    inVendorDevice = usb.util.CTRL_IN | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE


class SetupPacket(NamedTuple):
    bmRequestType: int
    bRequest: int
    wValue: int
    wIndex: int
    wLength: int
    packingFormat = "<BBHHH"


class StandardRequest(NamedTuple):
    bmRequestType: int
    bRequest: int


class StandardDeviceRequest(enum.IntEnum):
    GET_STATUS = 0x00
    CLEAR_FEATURE = 0x01
    SET_FEATURE = 0x03
    SET_ADDRESS = 0x05
    GET_DESCRIPTOR = 0x06
    SET_DESCRIPTOR = 0x07
    GET_CONFIGURATION = 0x08
    SET_CONFIGURATION = 0x09


class StandardDeviceRequestType(enum.IntEnum):
    GET_STATUS = usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE
    CLEAR_FEATURE = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE
    SET_FEATURE = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE
    SET_ADDRESS = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE
    GET_DESCRIPTOR = usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE
    SET_DESCRIPTOR = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE
    GET_CONFIGURATION = usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE
    SET_CONFIGURATION = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_DEVICE


class StandardInterfaceRequest(enum.IntEnum):
    GET_STATUS = 0x00
    CLEAR_FEATURE = 0x01
    SET_FEATURE = 0x03
    GET_INTERFACE = 0x0A
    SET_INTERFACE = 0x11


class StandardInterfaceRequestType(enum.IntEnum):
    GET_STATUS = usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_INTERFACE
    CLEAR_FEATURE = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_INTERFACE
    SET_FEATURE = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_INTERFACE
    GET_INTERFACE = usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_INTERFACE
    SET_INTERFACE = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_INTERFACE


class StandardEndpointRequest(enum.IntEnum):
    GET_STATUS = 0x00
    CLEAR_FEATURE = 0x01
    SET_FEATURE = 0x03
    SYNCH_FRAME = 0x12


class StandardEndpointRequestType(enum.IntEnum):
    GET_STATUS = usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_ENDPOINT
    CLEAR_FEATURE = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_ENDPOINT
    SET_FEATURE = usb.util.CTRL_OUT | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_ENDPOINT
    SYNCH_FRAME = usb.util.CTRL_IN | usb.util.CTRL_TYPE_STANDARD | usb.util.CTRL_RECIPIENT_ENDPOINT


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
    def testDescriptorPackingFormats(self):
        self.assertEqual(struct.calcsize(DeviceDescriptor.packingFormat), 18)
        self.assertEqual(struct.calcsize(ConfigurationDescriptor.packingFormat), 9)
        self.assertEqual(struct.calcsize(InterfaceDescriptor.packingFormat), 9)
        self.assertEqual(struct.calcsize(EndpointDescriptor.packingFormat), 7)

    def setUp(self):
        self.device = usb.core.find(idVendor=0x05ac, idProduct=0x1112)
        # self.assertIsNotNone(self.device)

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
        conf = self.device.get_active_configuration()
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

    def testEnums(self):
        print(StandardDeviceRequest.GET_STATUS)
        print(StandardDeviceRequestType.GET_STATUS)

    def testSendStatusControlRequest(self):
        ret = self.device.ctrl_transfer(StandardDeviceRequestType.GET_STATUS,
                                        bRequest=StandardDeviceRequest.GET_STATUS,
                                        wValue=0,
                                        wIndex=0,
                                        data_or_wLength=2)
        self.assertEqual(ret[0] | (ret[1] << 8), 0)

    def testGetDeviceDescriptor(self):
        ret = self.device.ctrl_transfer(StandardDeviceRequestType.GET_DESCRIPTOR,
                                        bRequest=StandardDeviceRequest.GET_DESCRIPTOR,
                                        wValue=(usb.util.DESC_TYPE_DEVICE << 8),
                                        wIndex=0,
                                        data_or_wLength=struct.calcsize(DeviceDescriptor.packingFormat))

        theStruct = struct.unpack(DeviceDescriptor.packingFormat, ret)
        desc = DeviceDescriptor(*theStruct)
        print(desc)

    def testGetConfigurationDescriptor(self):
        ret = self.device.ctrl_transfer(StandardDeviceRequestType.GET_CONFIGURATION,
                                        bRequest=StandardDeviceRequest.GET_DESCRIPTOR,
                                        wValue=(usb.util.DESC_TYPE_CONFIG << 8),
                                        wIndex=0,
                                        data_or_wLength=struct.calcsize(ConfigurationDescriptor.packingFormat))
        # print(ret)
        self.assertTrue(len(ret) >= 2)

        theStruct = struct.unpack(ConfigurationDescriptor.packingFormat, ret)
        desc = ConfigurationDescriptor(*theStruct)
        print(desc)

    def testGetCompleteConfigurationDescriptor(self):
        ret = self.device.ctrl_transfer(StandardDeviceRequestType.GET_CONFIGURATION,
                                        bRequest=StandardDeviceRequest.GET_DESCRIPTOR,
                                        wValue=(usb.util.DESC_TYPE_CONFIG << 8) | 0,
                                        wIndex=0,
                                        data_or_wLength=struct.calcsize(ConfigurationDescriptor.packingFormat))
        self.assertTrue(len(ret) >= 2)

        theStruct = struct.unpack(ConfigurationDescriptor.packingFormat, ret)
        desc = ConfigurationDescriptor(*theStruct)

        ret = self.device.ctrl_transfer(StandardDeviceRequestType.GET_CONFIGURATION,
                                        bRequest=StandardDeviceRequest.GET_DESCRIPTOR,
                                        wValue=(usb.util.DESC_TYPE_CONFIG << 8),
                                        wIndex=0,
                                        data_or_wLength=desc.wTotalLength)

        offset = 0
        configurationDescriptor = ConfigurationDescriptor(
            *struct.unpack_from(ConfigurationDescriptor.packingFormat, ret, offset))
        offset += configurationDescriptor.bLength

        interfaceAssociationDescriptor = InterfaceAssociationDescriptor(
            *struct.unpack_from(InterfaceAssociationDescriptor.packingFormat, ret, offset))
        offset += interfaceAssociationDescriptor.bLength

        self.assertEqual(interfaceAssociationDescriptor.bDescriptorType, DescriptorType.Interface_Association)
        self.assertEqual(interfaceAssociationDescriptor.bFunctionClass, 0x0e)
        self.assertEqual(interfaceAssociationDescriptor.bFunctionSubClass, 0x03)
        self.assertEqual(interfaceAssociationDescriptor.bFunctionProtocol, 0x00)

        for i in range(configurationDescriptor.bNumInterfaces):
            interfaceDescriptor = InterfaceDescriptor(
                *struct.unpack_from(InterfaceDescriptor.packingFormat, ret, offset))
            print(interfaceDescriptor)
            offset += interfaceDescriptor.bLength

            classSpecificDescriptor = ClassSpecificVCInterfaceDescriptor(
                *struct.unpack_from(ClassSpecificVCInterfaceDescriptor.packingFormat.format(0), ret, offset))
            print(classSpecificDescriptor)
            self.assertEqual(classSpecificDescriptor.bLength, 0x0d)
            self.assertEqual(classSpecificDescriptor.bDescriptorType, 0x24)
            self.assertEqual(classSpecificDescriptor.bDescriptorSubType, 0x01)
            # self.assertEqual(classSpecificDescriptor.bcdUVC, 0x0150)
            # self.assertEqual(classSpecificDescriptor.wTotalLength, 0x0042)
            self.assertEqual(classSpecificDescriptor.bInCollection, 0x01)
            classSpecificDescriptor = ClassSpecificVCInterfaceDescriptor(*struct.unpack_from(
                ClassSpecificVCInterfaceDescriptor.packingFormat.format(classSpecificDescriptor.bInCollection), ret,
                offset))

            offset += classSpecificDescriptor.bLength

            inputTerminalDescriptor = InputTerminalDescriptorCamera(
                *struct.unpack_from(InputTerminalDescriptorCamera.packingFormat, ret, offset))
            print(inputTerminalDescriptor)
            # self.assertEqual(inputTerminalDescriptor.bLength, struct.calcsize(InputTerminalDescriptorCamera.packingFormat))
            self.assertEqual(inputTerminalDescriptor.bDescriptorType, 0x24)
            self.assertEqual(inputTerminalDescriptor.bDescriptorSubType, 0x02)
            offset += inputTerminalDescriptor.bLength

            outputTerminalDescriptor = OutputTerminalDescriptor(
                *struct.unpack_from(OutputTerminalDescriptor.packingFormat, ret, offset))
            print(outputTerminalDescriptor)
            # self.assertEqual(inputTerminalDescriptor.bLength, struct.calcsize(InputTerminalDescriptorCamera.packingFormat))
            offset += outputTerminalDescriptor.bLength

            nextDescriptor = OutputTerminalDescriptor(
                *struct.unpack_from(OutputTerminalDescriptor.packingFormat, ret, offset))

            for e in range(interfaceDescriptor.bNumEndpoints):
                endpointDescriptor = EndpointDescriptor(
                    *struct.unpack_from(EndpointDescriptor.packingFormat, ret, offset))
                offset += struct.calcsize(EndpointDescriptor.packingFormat)
                print(endpointDescriptor)

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

    def unpackSingleDescriptor(self, data) -> ():
        descriptorsTypes = {DescriptorType.Device: DeviceDescriptor,
                           DescriptorType.Configuration: ConfigurationDescriptor,
                           DescriptorType.Interface: InterfaceDescriptor,
                           DescriptorType.Endpoint: EndpointDescriptor,
                           DescriptorType.String: StringDescriptor}

        csDescriptorSubTypes = {
            DescriptorSubType.VC_HEADER: ClassSpecificVCHeaderInterfaceDescriptor,
            DescriptorSubType.VC_INPUT_TERMINAL : ClassSpecificVCInputTerminalDescriptorComposite,
            DescriptorSubType.VC_OUTPUT_TERMINAL : ClassSpecificVCOutputTerminalDescriptor,
            DescriptorSubType.VC_SELECTOR_UNIT : ClassSpecificVCSelectorUnitDescriptor,
            DescriptorSubType.VC_PROCESSING_UNIT: ClassSpecificVCProcessingUnitDescriptor,
        }

        descriptor = UnknownDescriptor(*struct.unpack_from(UnknownDescriptor.packingFormat, data))
        descriptorBytes = data[:descriptor.bLength]
        remainingBytes = data[descriptor.bLength:]
        descriptor = UnknownDescriptor(*struct.unpack_from(UnknownDescriptor.packingFormat, descriptorBytes), bytes=descriptorBytes)

        try:
            if descriptor.bDescriptorType == DescriptorType.CS_INTERFACE:
                templateType = csDescriptorSubTypes[descriptor.bDescriptorSubType]
                descriptor = templateType(*struct.unpack_from(templateType.packingFormat, descriptorBytes))
            else:
                templateType = descriptorsTypes[descriptor.bDescriptorType]
                descriptor = templateType(*struct.unpack_from(templateType.packingFormat, descriptorBytes))
        except Exception as err:
            print(err)
            pass

        return descriptor, remainingBytes

    def unpackDescriptors(self, data):
        descriptors = []
        while len(data) > 0:
            descriptor, data = self.unpackSingleDescriptor(data)
            descriptors.append(descriptor)

        return descriptors

    def testUnpackDescriptors(self):
        offset = 0
        devices = usb.core.find(find_all=True, idVendor=0x5ac)
        self.assertIsNotNone(devices)

        for device in devices:
            ret = device.ctrl_transfer(StandardDeviceRequestType.GET_DESCRIPTOR,
                                            bRequest=StandardDeviceRequest.GET_DESCRIPTOR,
                                            wValue=(usb.util.DESC_TYPE_DEVICE << 8),
                                            wIndex=0,
                                            data_or_wLength=struct.calcsize(DeviceDescriptor.packingFormat))
            deviceDescriptor, bytes = self.unpackSingleDescriptor(ret)
            print(deviceDescriptor)

            ret = device.ctrl_transfer(StandardDeviceRequestType.GET_CONFIGURATION,
                                       bRequest=StandardDeviceRequest.GET_DESCRIPTOR,
                                       wValue=(usb.util.DESC_TYPE_CONFIG << 8) | 0,
                                       wIndex=0,
                                       data_or_wLength=struct.calcsize(ConfigurationDescriptor.packingFormat))
            self.assertTrue(len(ret) >= 2)

            theStruct = struct.unpack(ConfigurationDescriptor.packingFormat, ret)
            desc = ConfigurationDescriptor(*theStruct)

            data = device.ctrl_transfer(StandardDeviceRequestType.GET_CONFIGURATION,
                                        bRequest=StandardDeviceRequest.GET_DESCRIPTOR,
                                        wValue=(usb.util.DESC_TYPE_CONFIG << 8),
                                        wIndex=0,
                                        data_or_wLength=desc.wTotalLength)

            descriptors = self.unpackDescriptors(data)
            [ print("  ",d) for d in descriptors]


if __name__ == '__main__':
    unittest.main()
