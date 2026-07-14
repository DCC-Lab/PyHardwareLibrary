import env
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState
from hardwarelibrary.sources.verdig import (
    VerdiGDevice, DebugVerdiGDevice, HOPSInterface, DebugHOPSInterface)
from hardwarelibrary.sources.hopsnative import (
    HOPSNativeInterface, HOPSNativeI2C, MockHOPSBus)
from hardwarelibrary.capabilities import (
    OnOffCapability, ShutterCapability, PowerCapability, InterlockCapability, WavelengthCapability)
from hardwarelibrary.sources.lasersourcedevice import LaserSourceDevice

# Point at a real Verdi-G / HOPS laser on this host to exercise the hardware class.
NATIVE_URL = "ftdi://ftdi:0x6010:FTV5L9CA/1"


class TestVerdiGWithDebugInterface(unittest.TestCase):
    def setUp(self):
        self.laser = DebugVerdiGDevice()
        self.laser.initializeDevice()

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testAdvertisesFullCapabilitySet(self):
        self.assertIsInstance(self.laser, LaserSourceDevice)
        self.assertEqual(set(self.laser.capabilities()),
                         {OnOffCapability, ShutterCapability, PowerCapability, InterlockCapability})
        self.assertFalse(self.laser.hasCapability(WavelengthCapability))

    def testReadsIdentity(self):
        self.assertEqual(self.laser.laserModel, "Genesis CX-Vis")
        self.assertEqual(self.laser.headType, "G532")
        self.assertEqual(self.laser.headSerialNumber, "VH5359")
        self.assertAlmostEqual(self.laser.maxPower, 7.344, places=3)

    def testInitEnablesRemoteShutdownDisablesIt(self):
        self.assertTrue(self.laser.remoteControlIsOn())
        interface = self.laser.interface
        self.laser.shutdownDevice()
        self.assertFalse(interface.remoteOn())

    def testTurnOnOff(self):
        self.laser.turnOn()
        self.assertTrue(self.laser.isLaserOn())
        self.laser.turnOff()
        self.assertFalse(self.laser.isLaserOn())

    def testShutterRoundTrip(self):
        self.laser.openShutter()
        self.assertTrue(self.laser.isShutterOpen())
        self.laser.closeShutter()
        self.assertFalse(self.laser.isShutterOpen())

    def testSetPowerAndSetpoint(self):
        self.laser.setPower(3.0)
        self.assertAlmostEqual(self.laser.powerSetpoint(), 3.0, places=3)

    def testActualPowerNeedsEnableAndShutter(self):
        self.laser.setPower(2.0)
        self.assertEqual(self.laser.power(), 0.0)
        self.laser.turnOn()
        self.laser.openShutter()
        self.assertAlmostEqual(self.laser.power(), 2.0, places=3)

    def testRejectsOutOfRangePower(self):
        with self.assertRaises(ValueError):
            self.laser.setPower(self.laser.maxPower + 1.0)
        with self.assertRaises(ValueError):
            self.laser.setPower(-0.1)

    def testInterlockAndFaults(self):
        self.assertTrue(self.laser.interlock())
        self.assertEqual(self.laser.faults(), [])
        self.laser.interface.activeFaults = ["Interlock fault"]
        self.assertFalse(self.laser.interlock())
        self.assertIn("Interlock fault", self.laser.faults())

    def testStatusUserInfo(self):
        self.laser.turnOn(); self.laser.openShutter(); self.laser.setPower(1.5)
        info = self.laser.doGetStatusUserInfo()
        self.assertAlmostEqual(info["power"], 1.5, places=3)
        self.assertTrue(info["isLaserOn"])
        self.assertTrue(info["isShutterOpen"])
        self.assertTrue(info["remoteControl"])
        self.assertTrue(info["interlockOk"])


class TestInterfaceSelection(unittest.TestCase):
    def testPassingAnInterfaceInstanceUsesIt(self):
        interface = DebugHOPSInterface()
        laser = VerdiGDevice(interface=interface)
        laser.initializeDevice()
        self.assertIs(laser.interface, interface)
        laser.shutdownDevice()

    def testUnknownInterfaceChoiceRaises(self):
        laser = VerdiGDevice(interface="banana")
        with self.assertRaises(PhysicalDevice.UnableToInitialize):
            laser.initializeDevice()


class TestNativeInterfaceOnMock(unittest.TestCase):
    def setUp(self):
        self.interface = HOPSNativeInterface(bus=MockHOPSBus())
        self.laser = VerdiGDevice(interface=self.interface)
        self.laser.initializeDevice()

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testNativeReadsIdentity(self):
        self.assertEqual(self.laser.headType, "G532")
        self.assertEqual(self.laser.laserModel, "Genesis CX-Vis")

    def testNativeShutterAndEnableViaBits(self):
        self.laser.openShutter()
        self.assertTrue(self.laser.isShutterOpen())
        self.laser.turnOn()
        self.assertTrue(self.laser.isLaserOn())

    def testNativeSetPowerWritesDac(self):
        self.laser.setPower(3.0)
        self.assertEqual(self.interface._bus.dacCode,
                         int(round(3.0 * self.interface.dacCountsPerWatt)))

    def testNativeTemperatureCalibration(self):
        self.interface._bus.adc[0x94] = 1696
        self.assertAlmostEqual(self.laser.mainTemperature(), 32.222, places=2)

    def testNativeInterlockRaisesNotSupported(self):
        with self.assertRaises(HOPSInterface.NotSupported):
            self.laser.interlock()
        with self.assertRaises(HOPSInterface.NotSupported):
            self.laser.faults()

    def testNativePowerUncalibratedNonzeroRaises(self):
        self.interface._bus.adc[0xE4] = 1234
        with self.assertRaises(HOPSInterface.NotSupported):   # NotCalibrated subclass
            self.laser.power()


class TestHOPSNativeI2CReadModifyWrite(unittest.TestCase):
    def testWriteGpioBitPreservesOtherBits(self):
        bus = MockHOPSBus()
        i2c = HOPSNativeI2C(bus)
        bus.gpio[0x02] = 0b00000101
        i2c.writeGpioBit(5, 1)
        self.assertEqual(bus.gpio[0x02], 0b00100101)
        i2c.writeGpioBit(0, 0)
        self.assertEqual(bus.gpio[0x02], 0b00100100)


class TestVerdiGHardware(unittest.TestCase):
    def setUp(self):
        self.laser = VerdiGDevice(interface="native", url=NATIVE_URL)
        try:
            self.laser.initializeDevice()
        except PhysicalDevice.UnableToInitialize:
            self.skipTest("No native Verdi-G / HOPS laser reachable via pyftdi on this host")

    def tearDown(self):
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testReadsIdentity(self):
        self.assertIsNotNone(self.laser.headType)

    def testReadsTemperature(self):
        self.assertIsInstance(self.laser.mainTemperature(), float)

    def testReadsShutterState(self):
        self.assertIn(self.laser.isShutterOpen(), (True, False))


if __name__ == "__main__":
    unittest.main()
