import env
import unittest
import time

from hardwarelibrary.spectrometers.oceaninsight import (
    OISpectrometer, SpectrumRequestTimeoutError,
)


class MockOISpectrometer(OISpectrometer):
    """Hardware-free OISpectrometer for exercising getSpectrum() without USB.

    Bypasses the USB-connecting __init__ and stubs the three hooks getSpectrum
    relies on. `spectrumReady` controls whether the 'spectrum ready' flag rises.
    """

    def __init__(self, spectrumReady=False):
        self.spectrumReady = spectrumReady
        self.requestCount = 0

    def requestSpectrum(self):
        self.requestCount += 1

    def isSpectrumReady(self):
        return self.spectrumReady

    def getSpectrumData(self):
        return "spectrum"


class TestGetSpectrumBounded(unittest.TestCase):
    def testRaisesInsteadOfBlockingWhenNeverReady(self):
        device = MockOISpectrometer(spectrumReady=False)
        start = time.time()
        with self.assertRaises(SpectrumRequestTimeoutError):
            device.getSpectrum(maxRequests=2, maxWait=0.05)
        elapsed = time.time() - start
        self.assertLess(elapsed, 10.0)

    def testStopsAfterMaxRequests(self):
        device = MockOISpectrometer(spectrumReady=False)
        with self.assertRaises(SpectrumRequestTimeoutError):
            device.getSpectrum(maxRequests=2, maxWait=0.05)
        self.assertEqual(device.requestCount, 2)

    def testReturnsDataWhenReady(self):
        device = MockOISpectrometer(spectrumReady=True)
        self.assertEqual(device.getSpectrum(maxRequests=2, maxWait=0.05), "spectrum")
        self.assertEqual(device.requestCount, 1)


if __name__ == "__main__":
    unittest.main()
