import env
import unittest

from hardwarelibrary.physicaldevice import DeviceState
from hardwarelibrary.sources.cobolt import CoboltDevice
from hardwarelibrary.capabilities import (
    Capability, OnOffCapability, PowerCapability, InterlockCapability,
    AutostartCapability, WavelengthCapability, DispersionCapability)


class TestLaserCapabilities(unittest.TestCase):
    def setUp(self):
        self.device = CoboltDevice(portPath="debug")

    def tearDown(self):
        if self.device.state == DeviceState.Ready:
            self.device.shutdownDevice()

    def testCoboltAdvertisesItsFourCapabilities(self):
        self.assertEqual(set(self.device.capabilities()),
                         {OnOffCapability, PowerCapability, InterlockCapability, AutostartCapability})

    def testCapabilitiesExcludeTheMarkerAndUnsupportedOnes(self):
        self.assertNotIn(Capability, self.device.capabilities())
        self.assertNotIn(WavelengthCapability, self.device.capabilities())
        self.assertNotIn(DispersionCapability, self.device.capabilities())

    def testTypedDiscovery(self):
        self.assertIsInstance(self.device, PowerCapability)
        self.assertNotIsInstance(self.device, WavelengthCapability)

    def testHasCapability(self):
        self.assertTrue(self.device.hasCapability(PowerCapability))
        self.assertTrue(self.device.hasCapability(AutostartCapability))
        self.assertFalse(self.device.hasCapability(WavelengthCapability))

    def testDynamicAvailabilityOfTurnOn(self):
        self.device.initializeDevice()  # the debug Cobolt boots with autostart on
        self.assertTrue(self.device.autostartIsOn())
        self.assertFalse(self.device.canTurnOn())
        self.device.turnAutostartOff()
        self.assertTrue(self.device.canTurnOn())

    def testAutostartMethodsAreInheritedFromTheMixin(self):
        self.device.initializeDevice()
        self.device.turnAutostartOff()
        self.assertFalse(self.device.autostartIsOn())


if __name__ == "__main__":
    unittest.main()
