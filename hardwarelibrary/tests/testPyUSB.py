import env
import unittest

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

if __name__ == '__main__':
    unittest.main()
