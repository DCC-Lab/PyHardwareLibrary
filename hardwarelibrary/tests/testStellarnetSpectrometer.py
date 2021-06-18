import unittest
import time
import numpy as np
import matplotlib.pyplot as plt
import struct

from stellarnet import *

class TestStellarNetSpectrometer(unittest.TestCase):
    def test01CreateSpectro(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        
    def test02FindRawSpectro(self):
        rawDevices = StellarNet.findRawDevices()
        self.assertIsNotNone(rawDevices)
        self.assertTrue(len(rawDevices) <= 1)

    def test03ConfigureRawSpectro(self):
        rawDevices = StellarNet.findRawDevices()
        if len(rawDevices) > 0:
            StellarNet.loadFirmwareOnDevices(rawDevices)

        rawDevices = StellarNet.findRawDevices()
        self.assertTrue(len(rawDevices) == 0)

        usbDevices = StellarNet.connectedUSBDevices()
        self.assertTrue(len(usbDevices) > 0)

    def test04FindStelarNetSpectro(self):
        usbDevices = StellarNet.connectedUSBDevices()
        self.assertTrue(len(usbDevices) > 0)

    def test05FindStellarSpectrometer(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()

    def test06ReadBytes(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        bytes=spectro.doRead32Bytes(address=Address.deviceId)
        self.assertIsNotNone(bytes)

    def test07ReadBytes(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        for address in Address:
            try:
                data=spectro.doRead32Bytes(address=address)
                self.assertIsNotNone(data)
                #print("#{0:2X} : {1}".format(address, data))
            except Exception as err:
                pass
                #print("Unable to convert to string at # {0:2X}".format(address))
        
    def test07ReadString(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        for address in Address:
            try:
                string=spectro.doReadString(address=address)
                self.assertIsNotNone(string)
                # print("#{0:2X} : {1}".format(address, string))
            except Exception as err:
                pass
                #print("Unable to convert to string at # {0:2X}".format(address))

    def test07LookingForGainTab(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        for address in range(0x00, 0x100, 0x20):
            try:
                data=spectro.doRead32Bytes(address=address)
                self.assertIsNotNone(data)
                #print("#{0:02X} : {1}".format(address, data))
            except Exception as err:
                pass
                # print(err)
                #print("Unable to convert to string at # {0:2X}".format(address))

    def test08FIFO(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        self.assertTrue(spectro.hasLargeFIFO)

    def test09GetSpectrum(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        self.assertIsNotNone(spectro.getSpectrum())

    def test09ProgramFIFO(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        self.assertTrue(spectro.hasLargeFIFO)
        spectro.doProgramInternalFIFO()

    def test11Enum(self):
        self.assertIsNotNone(DetectorType("1"))

    def testEnumValues(self):
        for v in Address:
            v

    def test20SetIntegrationTime(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        self.assertTrue(spectro.hasLargeFIFO)
        spectro.doProgramInternalFIFO()
        spectro.setIntegrationTime(20)

    def test21SetTooSmallIntegrationTime(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        self.assertTrue(spectro.hasLargeFIFO)
        spectro.doProgramInternalFIFO()
        spectro.setIntegrationTime(1)

    def test30GetSpectrumShow(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()

        spectrum = spectro.getSpectrum()
        self.assertIsNotNone(spectrum)
        self.assertTrue(len(spectrum) == len(spectro.wavelength))

    def test40SpectroViewer(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()
        spectro.integrationTime = 100
        spectro.setIntegrationTime(100)
        SpectraViewer(spectro).display()

    def test100ReadGainTable(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()

        index = None
        if index is None:
            deviceIdentification = spectro.doGetDeviceIdentification()
            index = deviceIdentification.gainIndex

        self.assertTrue(index in [1,2,3,4,5])

        gainTable = spectro.doGetGainTable()
        self.assertTrue(len(gainTable) == 10)
        self.assertTrue( min(gainTable) != 0)

    def test110SetGain(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()

        index = None
        if index is None:
            deviceIdentification = spectro.doGetDeviceIdentification()
            index = deviceIdentification.gainIndex

        self.assertTrue(index in [1,2,3,4,5])

        gainTable = spectro.doGetGainTable()
        self.assertTrue(len(gainTable) == 10)
        self.assertTrue( min(gainTable) != 0)
        gain = gainTable[index-1]
        self.assertTrue(gain != 0)
        spectro.doWriteControlRequest(Request.setFIFOFlags, data= [0, gain, 0, 0])
        base = gainTable[(index-1)+5]
        self.assertTrue(base != 0)
        spectro.doWriteControlRequest(Request.setFIFOFlags, data= [1, base, 0, 0])

    def test120SetGain(self):
        spectro = StellarNet()
        self.assertIsNotNone(spectro)
        spectro.initializeDevice()

        spectro.saveGainToEEPROM()


if __name__ == "__main__":
    unittest.main()