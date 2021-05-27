import env # modifies path
import unittest
import time
from contextlib import redirect_stdout, redirect_stderr
import usb.core
import usb.util
import stellarnet_driver3 as sn
import io

class TestStellarNet(unittest.TestCase):
    def testInit(self):
        self.assertTrue(True)

    def testFindDevice(self):
        devices = sn.find_devices()
        self.assertTrue(len(devices) == 1)

    def testGetFirstDevice(self):
        devices = sn.find_devices()
        device = devices[0]
        self.assertIsNotNone(device)

    @unittest.expectedFailure
    def testGetDeviceInfo(self):
        devices = sn.find_devices()
        device = devices[0]

        # raises an exception after idVendor and idProduct
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                device.print_info()
                return
        except usb.core.USBError as err:
            pass

        lines = f.getvalue().split('\n')
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0] == '--- Device Information')
        self.assertTrue(lines[1] == 'idVendor:      0BD7')
        self.assertTrue(lines[2] == 'idProduct:     A012')
        self.assertTrue(lines[3] == '')
        self.fail("Unable to complete print_info()")

    def testGetDeviceConfig(self):
        devices = sn.find_devices()
        device = devices[0]
        cfg = device.get_config()
        self.assertIsNotNone(cfg)

    def testSetDeviceConfigIntegration10_1_1(self):
        devices = sn.find_devices()
        device = devices[0]
        device.set_config(int_time = 10, 
                          scans_to_avg = 1,
                          x_smooth = 1)

    def testSetDeviceConfigIntegrationTimeTooLow(self):
        devices = sn.find_devices()
        device = devices[0]
        with self.assertRaises(Exception):
            device.set_config(int_time = 1, 
                              scans_to_avg = 1,
                              x_smooth = 1)

    def testSetDeviceConfigAverageAtZero(self):
        devices = sn.find_devices()
        device = devices[0]
        with self.assertRaises(Exception):
            device.set_config(int_time = 10, 
                              scans_to_avg = 0,
                              x_smooth = 1)

    def testSetDeviceConfigAverageAt100(self):
        devices = sn.find_devices()
        device = devices[0]
        device.set_config(int_time = 10, 
                          scans_to_avg = 100,
                          x_smooth = 1)

    def testSetDeviceConfigSmoothingAtZeroIsOk(self):
        devices = sn.find_devices()
        device = devices[0]
        device.set_config(int_time = 10, 
                          scans_to_avg = 1,
                          x_smooth = 0)

    def testSetDeviceConfigSmoothingAt4IsMax(self):
        devices = sn.find_devices()
        device = devices[0]
        device.set_config(int_time = 10, 
                          scans_to_avg = 1,
                          x_smooth = 4)
        with self.assertRaises(Exception):
            device.set_config(int_time = 10, 
                              scans_to_avg = 1,
                              x_smooth = 5)

    def testGetFirstSpectrometer(self):
        spectrometer, wav = sn.array_get_spec(0)
        self.assertIsNotNone(spectrometer)
        self.assertIsNotNone(wav)

    def testGetSpectrometerList(self):
        for i in range(3):
            spectrometer, wav = sn.array_get_spec(i)
            self.assertIsNotNone(spectrometer)
            self.assertIsNotNone(wav)

    def testGetSpectrumWithLowValues(self):
        spectrometer, wav = sn.array_get_spec(0)
        device = spectrometer['device']
        device.set_config(int_time = 20, 
                          scans_to_avg = 1,
                          x_smooth = 1)
        spectrum = sn.array_spectrum(spectrometer, wav)
        self.assertEqual(len(spectrum), len(wav))

    def testFindMaximumIntegrationTime(self):
        spectrometer, wav = sn.array_get_spec(0)
        device = spectrometer['device']

        for t in (10, 15, 20, 25, 30 , 35):
            print("Should succeed at {0} ms".format(t))
            device.set_config(int_time = t, 
                              scans_to_avg = 1,
                              x_smooth = 1)
            spectrum = sn.array_spectrum(spectrometer, wav)
            self.assertEqual(len(spectrum), len(wav))

        for t in (50, 75, 100):
            print("Will fail at {0} ms".format(t))
            device.set_config(int_time = t, 
                              scans_to_avg = 1,
                              x_smooth = 1)
            with self.assertRaises(Exception):
                spectrum = sn.array_spectrum(spectrometer, wav)
                self.assertEqual(len(spectrum), len(wav))


if __name__ == '__main__':
    unittest.main()
