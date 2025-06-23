import env
import unittest
from hardwarelibrary.photoncounters.hamamatsu import HamamatsuH11890Device


class TestHamamatsuClass(unittest.TestCase):
    def setUp(self):
        self.device = HamamatsuH11890Device()
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()

    def testIntegration(self):
        self.device.set_integration_time(10000)
        _, actualIntegrationTime = self.device.get_integration_time()
        self.assertEqual(actualIntegrationTime, 10000)

    def testBadCommand(self):
        with self.assertRaises(HamamatsuH11890Device.BadCommand):
            self.device.sendCommand('B')

    def testRepetition2(self):
        self.device.set_repetition(123)
        _, actualRepetitions = self.device.get_repetition()
        self.assertEqual(actualRepetitions, 123)

    def testStartStop(self):
        self.device.start_counting()
        self.device.stop_counting()

    def testStartFetchStop(self):
        self.device.set_repetition(0)
        self.device.set_integration_time(10000)
        self.device.start_counting(correction=True)
        self.device.fetchOne()
        self.device.stop_counting()

    def testStartFetchStopWithoutCorrection(self):
        self.device.set_repetition(0)
        self.device.set_integration_time(10000)
        self.device.start_counting(correction=False)
        self.device.fetchOne()
        self.device.stop_counting()

    def testStartFetchAllStop(self):
        self.device.set_repetition(10)
        self.device.set_integration_time(10000)
        self.device.start_counting()
        counts = self.device.fetchAll(maxIndex=10)
        for i, (idx, c) in enumerate(counts):
            self.assertEqual(i, idx)
            self.assertTrue(c > 0)
        self.device.stop_counting()

    def testStartWaitFetchAllStop(self):
        self.device.set_repetition(10)
        self.device.set_integration_time(10000)
        self.device.start_counting()
        counts = self.device.fetchAll(maxIndex=10)
        for i, (idx, c) in enumerate(counts):
            self.assertEqual(i, idx)
            self.assertTrue(c > 0,"{0}".format(c))
            self.assertTrue(c & 0x8000 == 0)
        self.device.stop_counting()

    def testStopStop(self):
        self.device.stop_counting()
        self.device.stop_counting()

    def testTurnOnAndOff(self):
        self.device.turn_on()
        self.device.turn_off()

    def testSetDefaultVoltage(self):
        print(self.device.set_high_voltage())
        _, actualVoltage = self.device.get_high_voltage()
        self.assertEqual(actualVoltage, 1000)

    def testSetNullVoltage(self):
        self.device.set_high_voltage(0)
        _, actualVoltage = self.device.get_high_voltage()
        self.assertEqual(actualVoltage, 0)

    def testSetSomeVoltage(self):
        self.device.set_high_voltage(800)
        _, actualVoltage = self.device.get_high_voltage()
        self.assertEqual(actualVoltage, 800)

    def testSetDefaultManuallyOnlyD(self):
        with self.assertRaises(HamamatsuH11890Device.BadCommand):
            self.device.sendCommand('D') # it's really DV


if __name__ == '__main__':
    unittest.main()
