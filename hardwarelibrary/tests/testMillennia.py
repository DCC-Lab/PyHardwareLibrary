import env
import os
import time
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.sources.millennia import (
    MillenniaEv25Device, DebugMillenniaEv25Device,
    MillenniaDevice, DebugMillenniaDevice,
)
from hardwarelibrary.capabilities import (
    OnOffCapability, ShutterCapability, PowerCapability, InterlockCapability, WavelengthCapability)
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
        self.assertIsInstance(self.laser, OnOffCapability)
        self.assertIsInstance(self.laser, ShutterCapability)
        self.assertIsInstance(self.laser, PowerCapability)

    def testAdvertisesOnOffShutterAndPower(self):
        self.assertEqual(set(self.laser.capabilities()),
                         {OnOffCapability, ShutterCapability, PowerCapability})

    def testDoesNotAdvertiseUnsupportedCapabilities(self):
        for unsupported in (InterlockCapability, WavelengthCapability):
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

    def testStatusUserInfoSnapshotsPowerOnOffAndShutter(self):
        self.laser.setPower(7.5)
        self.laser.turnOn()
        self.laser.openShutter()
        self.assertEqual(
            self.laser.doGetStatusUserInfo(),
            {"power": 7.5, "isLaserOn": True, "isShutterOpen": True},
        )


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
            # The eV refuses a setpoint change while still ramping, so let the
            # output settle before restoring; then setPower confirms via ?PSET.
            if self.originalSetpoint is not None:
                self.waitForPowerToSettle()
                self.laser.setPower(self.originalSetpoint)
            if self.originalShutterOpen:
                self.laser.openShutter()
            else:
                self.laser.closeShutter()
            self.laser.shutdownDevice()

    def waitForPowerToSettle(self, attempts=30, interval=0.5, stability=0.05):
        previous = float(self.laser.queryString("?P").split()[0])
        for _ in range(attempts):
            time.sleep(interval)
            current = float(self.laser.queryString("?P").split()[0])
            if abs(current - previous) < stability:
                return
            previous = current

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
                           min(self.laser.maxPower, self.originalSetpoint - 1.0)), 2)
        # setPower raises UnableToConfirmSetpoint if the write never lands; on
        # success ?PSET already matches, which we re-check here end to end.
        self.laser.setPower(target)
        self.assertAlmostEqual(float(self.laser.queryString("?PSET")), target, places=2)


if __name__ == "__main__":
    unittest.main()
