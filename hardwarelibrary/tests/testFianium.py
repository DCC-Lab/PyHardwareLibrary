import env
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.sources.fianium import (
    FianiumLaserDevice, DebugFianiumLaserDevice, FianiumManualInterventionRequired,
)
from hardwarelibrary.capabilities import (
    OnOffCapability, TemperatureCapability, PulsePickerCapability,
    ShutterCapability, PowerCapability, InterlockCapability,
    AutostartCapability, WavelengthCapability, DispersionCapability,
)
from hardwarelibrary.sources.lasersourcedevice import LaserSourceDevice


class TestDebugFianiumLaserDevice(unittest.TestCase):
    def setUp(self):
        self.laser = DebugFianiumLaserDevice()
        self.laser.initializeDevice()

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testIsLaserSourceWithExpectedCapabilities(self):
        self.assertIsInstance(self.laser, LaserSourceDevice)
        self.assertIsInstance(self.laser, OnOffCapability)
        self.assertIsInstance(self.laser, TemperatureCapability)
        self.assertIsInstance(self.laser, PulsePickerCapability)

    def testAdvertisesOnOffTemperatureAndPulsePicker(self):
        self.assertEqual(set(self.laser.capabilities()),
                         {OnOffCapability, TemperatureCapability, PulsePickerCapability})

    def testDoesNotAdvertiseUnsupportedCapabilities(self):
        for unsupported in (ShutterCapability, PowerCapability, InterlockCapability,
                            AutostartCapability, WavelengthCapability, DispersionCapability):
            self.assertFalse(self.laser.hasCapability(unsupported))

    def testInitializeReadsIdentity(self):
        self.assertEqual(self.laser.firmwareVersion, "Issue 5.17 20th February 2012")

    def testStartsOff(self):
        self.assertFalse(self.laser.isLaserOn())

    def testIsLaserOnTracksDriveAndPreamp(self):
        self.assertFalse(self.laser.isLaserOn())
        self.laser.simulatedPumaDrive = 238
        self.laser.simulatedPreamp = 2207  # matches the bench reading once lasing
        self.assertTrue(self.laser.isLaserOn())

    def testIsLaserOnStaysFalseIfOnlyDriveIsNonZero(self):
        # Drive alone, without the preamp photodiode confirming the seed is
        # running, must not read as "on": see seedDetectionThreshold.
        self.laser.simulatedPumaDrive = 5
        self.laser.simulatedPreamp = 10
        self.assertFalse(self.laser.isLaserOn())

    def testTurnOnRaisesManualInterventionRequired(self):
        with self.assertRaises(FianiumManualInterventionRequired):
            self.laser.turnOn()

    def testTurnOffRaisesManualInterventionRequired(self):
        with self.assertRaises(FianiumManualInterventionRequired):
            self.laser.turnOff()

    def testDiagnosticsReadBack(self):
        self.assertEqual(self.laser.controlMode(), "Pot controlled open loop mode")
        self.assertEqual(self.laser.heaterStatus(), "Laser Temperature ready")
        self.assertAlmostEqual(self.laser.temperature(), 20.5, places=1)
        self.assertEqual(self.laser.alarms(), "No alarms")
        self.assertEqual(self.laser.amplifierDrive(), (0, 0))
        self.assertEqual(self.laser.preampPhotodiode(), 10)
        self.assertEqual(self.laser.backReflectionPhotodiode(), 12)
        self.assertEqual(self.laser.runningHours(), "Time elapsed = 0 hours 0 minutes")
        self.assertAlmostEqual(self.laser.pulsePickerFrequency(), 2.0e6, places=0)

    def testStatusUserInfoSnapshot(self):
        info = self.laser.doGetStatusUserInfo()
        self.assertEqual(info["firmwareVersion"], "Issue 5.17 20th February 2012")
        self.assertEqual(info["alarms"], "No alarms")
        self.assertEqual(info["controlMode"], "Pot controlled open loop mode")
        self.assertFalse(info["isLaserOn"])


class TestFianiumLaserDevice(unittest.TestCase):
    def setUp(self):
        # No portPath/serialNumber on purpose: exercises the real FTDI-adaptor
        # discovery and identity check in doInitializeDevice, not a pinned port.
        self.laser = FianiumLaserDevice()
        try:
            self.laser.initializeDevice()
        except PhysicalDevice.UnableToInitialize:
            self.skipTest("No Fianium laser found on any FTDI adaptor")

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testIdentityWasConfirmedByACommand(self):
        self.assertIsNotNone(self.laser.firmwareVersion)
        self.assertTrue(self.laser.firmwareVersion.startswith("Issue"))

    def testReadOnlyDiagnostics(self):
        self.assertIsInstance(self.laser.temperature(), float)
        self.assertIsInstance(self.laser.alarms(), str)
        self.assertIsInstance(self.laser.controlMode(), str)
        pumaDrive, dac = self.laser.amplifierDrive()
        self.assertIsInstance(pumaDrive, int)
        self.assertIsInstance(dac, int)
        self.assertIsInstance(self.laser.runningHours(), str)
        self.assertIsInstance(self.laser.pulsePickerFrequency(), float)

    def testTurnOnRaisesManualInterventionRequired(self):
        # Safe to call against real hardware: this only queries M? and raises,
        # it never writes M= or Q=.
        with self.assertRaises(FianiumManualInterventionRequired):
            self.laser.turnOn()

    def testStatusUserInfoSnapshot(self):
        info = self.laser.doGetStatusUserInfo()
        for key in ("firmwareVersion", "temperature", "alarms", "controlMode",
                    "pumaDrive", "dac", "preampPhotodiode",
                    "backReflectionPhotodiode", "isLaserOn"):
            self.assertIn(key, info)


if __name__ == "__main__":
    unittest.main()
