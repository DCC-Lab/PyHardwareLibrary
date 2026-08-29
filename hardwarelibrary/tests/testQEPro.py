import struct
import unittest

import numpy as np

from hardwarelibrary.physicaldevice import DeviceState
from hardwarelibrary.spectrometers.qepro import QEPro, DebugQEPro


class TestDebugQEPro(unittest.TestCase):
    def setUp(self):
        self.spectrometer = DebugQEPro()
        self.spectrometer.initializeDevice()

    def tearDown(self):
        self.spectrometer.shutdownDevice()

    def testInitializeBringsDeviceToReady(self):
        self.assertEqual(self.spectrometer.state, DeviceState.Ready)

    def testWavelengthArrayHasActivePixelLength(self):
        self.assertEqual(len(self.spectrometer.wavelength), QEPro.activePixelCount)

    def testWavelengthFromCoefficients(self):
        coefficients = self.spectrometer._wavelengthCoefficients
        self.assertAlmostEqual(self.spectrometer.wavelength[0], coefficients[0], places=4)

    def testGetSerialNumber(self):
        self.assertEqual(self.spectrometer.getSerialNumber(), 'QEPDEBUG')

    def testGetIntegrationTimeAfterSet(self):
        self.spectrometer.setIntegrationTime(250_000)
        self.assertEqual(self.spectrometer.getIntegrationTime(), 250_000)

    def testSetIntegrationTimeBelowMinimumRaises(self):
        with self.assertRaises(ValueError):
            self.spectrometer.setIntegrationTime(QEPro.minIntegrationTimeMicroSec - 1)

    def testSetIntegrationTimeAboveMaximumRaises(self):
        with self.assertRaises(ValueError):
            self.spectrometer.setIntegrationTime(QEPro.maxIntegrationTimeMicroSec + 1)

    def testSetIntegrationTimeAtMinimumIsAccepted(self):
        self.spectrometer.setIntegrationTime(QEPro.minIntegrationTimeMicroSec)
        self.assertEqual(self.spectrometer.integrationTime,
                         QEPro.minIntegrationTimeMicroSec)

    def testGetSpectrumReturnsActivePixelCount(self):
        spectrum = self.spectrometer.getSpectrum()
        self.assertEqual(len(spectrum), QEPro.activePixelCount)

    def testGetSpectrumValuesAreMasked(self):
        spectrum = self.spectrometer.getSpectrum()
        self.assertTrue((spectrum <= QEPro.pixelMask).all())

    def testGetSpectrumHasPeak(self):
        spectrum = self.spectrometer.getSpectrum()
        peakPixel = int(np.argmax(spectrum))
        self.assertGreater(spectrum[peakPixel], spectrum[0])
        self.assertGreater(spectrum[peakPixel], spectrum[-1])

    def testSpecCountIncrementsAcrossAcquisitions(self):
        self.spectrometer.getSpectrum()
        firstCount = self.spectrometer._specCount
        self.spectrometer.getSpectrum()
        self.assertEqual(self.spectrometer._specCount, firstCount + 1)

    def testShutdownLeavesDeviceInRecognizedState(self):
        self.spectrometer.shutdownDevice()
        self.assertNotEqual(self.spectrometer.state, DeviceState.Ready)


class TestQEPro(unittest.TestCase):
    def setUp(self):
        try:
            self.spectrometer = QEPro()
            self.spectrometer.initializeDevice()
        except Exception as err:
            self.skipTest(f"No QE Pro spectrometer connected: {err}")

    def tearDown(self):
        if getattr(self, 'spectrometer', None) is not None:
            self.spectrometer.shutdownDevice()

    def testReadsSerialNumber(self):
        serial = self.spectrometer.getSerialNumber()
        self.assertIsInstance(serial, str)
        self.assertGreater(len(serial), 0)

    def testGetSpectrum(self):
        spectrum = self.spectrometer.getSpectrum()
        self.assertEqual(len(spectrum), QEPro.activePixelCount)

    def testIntegrationTimeRoundTrip(self):
        target = 100_000
        self.spectrometer.setIntegrationTime(target)
        self.assertEqual(self.spectrometer.getIntegrationTime(), target)


if __name__ == '__main__':
    unittest.main()
