import env
import unittest
import hardwarelibrary.utils as utils
import usb.core

class PyUSBTestCase(unittest.TestCase):
    def testDiagnoseDefaultBackendPresent(self):
        import usb.backend.libusb1
        backend = usb.backend.libusb1.get_backend()
        if backend is None:
            print("Default backend not found")

            from hardwarelibrary.communication import validateUSBBackend
            validateUSBBackend(False)
            backend = usb.backend.libusb1.get_backend()
            self.assertIsNotNone(backend)
            print("After validation, backend found at {0}".format(backend.lib))
        else:
            print("Default backend found at {0}".format(backend.lib))

    def testValidateBackendVerbose(self):
        import usb.backend.libusb1
        from hardwarelibrary.communication import validateUSBBackend
        validateUSBBackend(verbose=True)
        backend = usb.backend.libusb1.get_backend()
        self.assertIsNotNone(backend)

    def testUtilsConnectedDevices(self):
        devices = utils.connectedUSBDevices()
        if len(devices) == 0:
            self.skipTest("No USB devices connected")

    def testUtilsAppleConnectedDevices(self):
        devices = utils.connectedUSBDevices( [(0x05ac,0x8104)])
        if len(devices) == 0:
            self.skipTest("No Apple USB device connected")

    def testUtilsRazrConnectedDevices(self):
        devices = utils.connectedUSBDevices( [(0x1532,0x0067)])
        if len(devices) == 0:
            self.skipTest("No Razer device connected")
        self.assertTrue(len(devices) == 1)

    def testUtilsUniqueRazrConnectedDevices(self):
        try:
            device = utils.uniqueUSBDevice( [(0x1532,0x0067)])
            self.assertIsNotNone(device)
        except Exception:
            self.skipTest("No Razer device connected")

    def testUtilsAnyRazrConnectedDevices(self):
        try:
            device = utils.anyUSBDevice( [(0x1532,0x0067)])
            self.assertIsNotNone(device)
        except Exception:
            self.skipTest("No Razer device connected")

    def testUtilsFakeConnectedDevices(self):
        devices = utils.connectedUSBDevices( [(0x1532,0x0000)])
        self.assertEqual(len(devices), 0)
        devices = utils.connectedUSBDevices( [(0x0000, 0x0067)])
        self.assertEqual(len(devices), 0)
        devices = utils.connectedUSBDevices( [(0x0000,0x0000)])
        self.assertEqual(len(devices), 0)

if __name__ == '__main__':
    unittest.main()
