import env
import os
import time
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.sources.millennia import (
    MillenniaEv25Device, DebugMillenniaEv25Device,
    MillenniaDevice, DebugMillenniaDevice,
)
from hardwarelibrary.sources.capabilities import (
    OnOffControl, ShutterControl, PowerControl, InterlockControl, WavelengthControl)
from hardwarelibrary.sources.lasersourcedevice import LaserSourceDevice

# Set to the serial port of an attached Millennia eV to exercise TestMillenniaEv25Device;
# the tests skip when no laser answers there.
MILLENNIA_PORT = "/dev/cu.usbserial-MILLENNIA"

# Tests that open the shutter or change the pump power fire live emission and
# move real output. They stay skipped unless the operator has blocked the beam
# and explicitly opted in with MILLENNIA_BEAM_TESTS=1, so a routine hardware
# test run can never open the shutter unexpectedly.
BEAM_TESTS_ENABLED = os.environ.get("MILLENNIA_BEAM_TESTS") == "1"


class TestDebugMillenniaEv25Device(unittest.TestCase):
    def setUp(self):
        self.laser = DebugMillenniaEv25Device()
        self.laser.initializeDevice()

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testIsLaserSourceWithOnOffShutterAndPowerCapabilities(self):
        self.assertIsInstance(self.laser, LaserSourceDevice)
        self.assertIsInstance(self.laser, OnOffControl)
        self.assertIsInstance(self.laser, ShutterControl)
        self.assertIsInstance(self.laser, PowerControl)

    def testAdvertisesOnOffShutterAndPower(self):
        self.assertEqual(set(self.laser.capabilities()),
                         {OnOffControl, ShutterControl, PowerControl})

    def testDoesNotAdvertiseUnsupportedCapabilities(self):
        for unsupported in (InterlockControl, WavelengthControl):
            self.assertFalse(self.laser.hasCapability(unsupported))

    def testStartsOffWithShutterClosed(self):
        self.assertFalse(self.laser.isLaserOn())
        self.assertFalse(self.laser.isShutterOpen())

    def testTurnOnOffRoundTrip(self):
        self.laser.turnOn()
        self.assertTrue(self.laser.isLaserOn())
        self.laser.turnOff()
        self.assertFalse(self.laser.isLaserOn())

    def testShutterOpenCloseRoundTrip(self):
        self.laser.openShutter()
        self.assertTrue(self.laser.isShutterOpen())
        self.laser.closeShutter()
        self.assertFalse(self.laser.isShutterOpen())

    def testSetAndReadPowerRoundTrip(self):
        self.laser.setPower(4.95)
        self.assertAlmostEqual(self.laser.power(), 4.95, places=2)

    def testRejectsPowerBelowMinimum(self):
        with self.assertRaises(ValueError):
            self.laser.setPower(0.0)

    def testRejectsPowerAboveMaximum(self):
        with self.assertRaises(ValueError):
            self.laser.setPower(30.0)

    def testAcceptsPowerAtBoundaries(self):
        self.laser.setPower(self.laser.minPower)
        self.assertAlmostEqual(self.laser.power(), self.laser.minPower, places=2)
        self.laser.setPower(self.laser.maxPower)
        self.assertAlmostEqual(self.laser.power(), self.laser.maxPower, places=2)

    def testMillenniaDeviceAliasesEv25Device(self):
        self.assertIs(MillenniaDevice, MillenniaEv25Device)
        self.assertIs(DebugMillenniaDevice, DebugMillenniaEv25Device)
        self.assertIsInstance(self.laser, MillenniaDevice)

    def testInitializeReadsAndParsesIdentity(self):
        self.assertEqual(self.laser.manufacturer, "Spectra_Physics")
        self.assertEqual(self.laser.model, "Millennia eV")
        self.assertEqual(self.laser.laserSerialNumber, "3239")
        self.assertEqual(self.laser.firmwareVersion, "214-00.004.096/CD00000019")

    def testShutterIsIndependentOfOnOff(self):
        self.laser.turnOn()
        self.assertTrue(self.laser.isLaserOn())
        self.assertFalse(self.laser.isShutterOpen())  # on, but still blocked

        self.laser.openShutter()
        self.assertTrue(self.laser.isLaserOn())
        self.assertTrue(self.laser.isShutterOpen())

        self.laser.turnOff()
        self.assertFalse(self.laser.isLaserOn())
        self.assertTrue(self.laser.isShutterOpen())  # off, shutter unchanged


class TestMillenniaEv25Device(unittest.TestCase):
    def setUp(self):
        self.laser = MillenniaEv25Device(portPath=MILLENNIA_PORT)
        try:
            self.laser.initializeDevice()
        except PhysicalDevice.UnableToInitialize:
            self.skipTest("No Millennia eV reachable at {0}".format(MILLENNIA_PORT))
        # Snapshot the setpoint and shutter so the write tests below can leave
        # the pump laser exactly as they found it. ?PSET echoes the commanded
        # setpoint (unlike ?P, the slowly-ramping actual output).
        setpoint = self.laser.queryString("?PSET")
        self.originalSetpoint = float(setpoint) if setpoint else None
        self.originalShutterOpen = self.laser.isShutterOpen()

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            if self.originalSetpoint is not None:
                self.setPowerWithRetry(self.originalSetpoint)
            if self.originalShutterOpen:
                self.laser.openShutter()
            else:
                self.laser.closeShutter()
            self.laser.shutdownDevice()

    def setPowerWithRetry(self, target, attempts=8):
        # P: writes are intermittently dropped on the eV's USB-CDC link, and the
        # eV does not ack action commands, so a lost write goes unnoticed.
        # Confirm against ?PSET (the echoed setpoint, not the slowly-ramping ?P),
        # giving the unit a moment to commit before reading back, and retry.
        # Returns True once ?PSET matches, False if it never did or the firmware
        # does not echo ?PSET.
        for _ in range(attempts):
            self.laser.setPower(target)
            time.sleep(0.2)
            echoed = self.laser.queryString("?PSET")
            if not echoed:
                return False
            if abs(float(echoed) - target) < 0.005:
                return True
        return False

    def requireBeamTestsEnabled(self):
        if not BEAM_TESTS_ENABLED:
            self.skipTest(
                "Opens the shutter / changes pump power. Block the beam and set "
                "MILLENNIA_BEAM_TESTS=1 to run it.")

    def testReadsOnOffState(self):
        self.assertIn(self.laser.isLaserOn(), (True, False))

    def testReadsShutterState(self):
        self.assertIn(self.laser.isShutterOpen(), (True, False))

    def testReadsPower(self):
        self.assertIsInstance(self.laser.power(), float)

    def testReadsIdentity(self):
        self.assertIsNotNone(self.laser.idn)
        self.assertIn("Millennia", self.laser.idn)

    def testOpenCloseShutterRoundTrip(self):
        self.requireBeamTestsEnabled()
        self.laser.openShutter()
        self.assertTrue(self.laser.isShutterOpen())
        self.laser.closeShutter()
        self.assertFalse(self.laser.isShutterOpen())

    def testSetPowerUpdatesSetpoint(self):
        self.requireBeamTestsEnabled()
        if self.originalSetpoint is None:
            self.skipTest("Firmware does not echo a setpoint via ?PSET")
        # Verify against ?PSET (the commanded setpoint, updated immediately),
        # not ?P (actual output, which ramps over several seconds).
        target = round(max(self.laser.minPower,
                           min(self.laser.maxPower, self.originalSetpoint - 2.0)), 2)
        self.assertTrue(self.setPowerWithRetry(target),
                        "Millennia did not accept setpoint {0:.2f} W".format(target))
        self.assertAlmostEqual(float(self.laser.queryString("?PSET")), target, places=2)


if __name__ == "__main__":
    unittest.main()
