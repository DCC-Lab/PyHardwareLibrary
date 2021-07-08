import env # modifies path
import unittest
from io import StringIO
import pyftdi.serialext
from pyftdi.ftdi import Ftdi
from pyftdi.usbtools import UsbDeviceDescriptor, UsbTools
from serial.tools.list_ports import comports
import re

class TestPyFTDIModule(unittest.TestCase):
    def testShowDevicesReturnsNothing(self):
        portList = StringIO()
        a = Ftdi.show_devices(out=portList)
        self.assertIsNone(a)
        self.assertIsNotNone(portList)

    def testShowDevicesCanRedirectStdout(self):
        portList = StringIO()
        Ftdi.show_devices(out=portList)
        # print("{0}".format(portList.getvalue()))
        self.assertTrue(len(portList.getvalue()) > 0)

    def testShowDevicesExtractURLs(self):
        portList = StringIO()
        Ftdi.show_devices(out=portList)
        text = portList.getvalue()
        self.assertTrue(len(text) > 0)

        urls = []
        for someText in text.split():
            if re.match("ftdi://",someText,re.IGNORECASE):
                urls.append(someText)

    def availableFTDIURLs(self):
        portList = StringIO()
        Ftdi.show_devices(out=portList)
        everything = portList.getvalue()

        urls = []
        for someText in everything.split():
            if re.match("ftdi://",someText,re.IGNORECASE):
                urls.append(someText)

        return urls

    def testURLFinding(self):
        urls = self.availableFTDIURLs()
        self.assertTrue(len(urls) == 1)
        

if __name__ == '__main__':
    unittest.main()
