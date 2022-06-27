import env
import unittest
from io import StringIO
import unittest
from io import StringIO

import pyftdi.serialext
from pyftdi.ftdi import Ftdi


class TestPyFTDIModule(unittest.TestCase):
    def setUp(self):
        portList = StringIO()

        try:
            idVendor = 4930
            idProduct = 1

            pyftdi.ftdi.Ftdi.add_custom_product(vid=idVendor, pid=idProduct, pidname='VID {0}: PID {1}'.format(idVendor, idProduct))
        except Exception as err:
            print(err)        

        Ftdi.show_devices(out=portList)
        self.assertIsNotNone(portList)
        print("{0}".format(portList.getvalue()))
        if len(portList.getvalue()) == 0:
            raise(unittest.SkipTest("No FTDI connected. Skipping."))

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
