import env
import os
import unittest

from hardwarelibrary.communication.serialport import SerialPort

hardcodedPath = '/dev/tty.usbmodem143101'

class TestOptotune(unittest.TestCase):
    idVendor = 0x03eb
    idProduct = 0x2018

    def setUp(self):
        if not os.path.exists(hardcodedPath):
            raise(unittest.SkipTest("No OptoTune connected. Skipping."))

    # def asString(self, bytesRead):
    #     return bytes(bytesRead[:-2]).decode()

    # def testGetAnyDevice(self):
    #     self.assertIsNotNone(usb.core.find())

    # def testGetThisDevice(self):
    #     dev = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
    #     self.assertIsNotNone(dev)

    # def testUSBPort(self):
    #     self.assertIsNotNone(USBPort(idVendor=self.idVendor, interfaceNumber=1))

    # def testOptotuneManual(self):
    #     dev = usb.core.find(idVendor=self.idVendor)
    #     dev.reset()
    #     for config in dev:
    #         for i in range(config.bNumInterfaces):
    #             if dev.is_kernel_driver_active(i):
    #                 print("Detaching")
    #                 dev.detach_kernel_driver(i)
    #             else:
    #                 print("Not attached")
    #     # dev.reset()
    #     dev.set_configuration()
    #     # usb.util.claim_interface(dev, 1)
    #     conf = dev.get_active_configuration()

    # #     dev.set_configuration()
    #     # print(conf)
    #     intf0 = conf[(0,0)]
    #     intf1 = conf[(1,0)]
    #     # #print(intf)
    #     epOut = intf1[0]
    #     # print(epOut)
    #     epIn = intf1[1]
    #     # print(epIn)
    #     self.assertEqual(epOut.write(b'Start\r'), 6)
    #     print(epIn.read(size_or_buffer=7, timeout=5000))
    #     # print(intf0[0].read(size_or_buffer=7, timeout=5000))
    #     usb.util.dispose_resources(dev)
    def testSerialPort(self):
        port = SerialPort(portPath='/dev/tty.usbmodem143101')
        self.assertIsNotNone(port)
        port.open()
        self.assertTrue(port.isOpen)
        reply = port.writeStringExpectMatchingString(string='Start', replyPattern='.*')
        print(reply)
        port.close()
    # def testOptotuneUSBPort(self):
    #     optotune = USBPort(idVendor=self.idVendor, interfaceNumber=1)
    #     intf = optotune.interface
    #     #print(intf)
    #     epOut = intf[0]
    #     print(epOut)
    #     epIn = intf[1]
    #     print(epIn)
    #     self.assertEqual(epOut.write(b'Start\r'), 6)
    #     print(epIn.read(size_or_buffer=7, timeout=1000))

    # def testOptotuneCommand(self):
    #     optotune = USBPort(idVendor=self.idVendor, interfaceNumber=1)
    #     intf = optotune.interface
    #     #print(intf)
    #     epOut = intf[0]
    #     print(epOut)
    #     epIn = intf[1]
    #     print(epIn)
    #     self.assertEqual(epOut.write(b'Start\r'), 6)
    #     print(epIn.read(size_or_buffer=7, timeout=1000))



if __name__ == '__main__':
    unittest.main()
