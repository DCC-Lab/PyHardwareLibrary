import env
import unittest

from hardwarelibrary.physicaldevice import DeviceState
from hardwarelibrary.sources.cobolt import CoboltDevice
from hardwarelibrary.sources.capabilities import (
    Capability, OnOffControl, PowerControl, InterlockControl,
    AutostartControl, WavelengthControl)


class TestLaserCapabilities(unittest.TestCase):
    def setUp(self):
        self.device = CoboltDevice(portPath="debug")

    def tearDown(self):
        if self.device.state == DeviceState.Ready:
            self.device.shutdownDevice()

    def testCoboltAdvertisesItsFourCapabilities(self):
        self.assertEqual(set(self.device.capabilities()),
                         {OnOffControl, PowerControl, InterlockControl, AutostartControl})

    def testCapabilitiesExcludeTheMarkerAndUnsupportedOnes(self):
        self.assertNotIn(Capability, self.device.capabilities())
        self.assertNotIn(WavelengthControl, self.device.capabilities())

    def testTypedDiscovery(self):
        self.assertIsInstance(self.device, PowerControl)
        self.assertNotIsInstance(self.device, WavelengthControl)

    def testHasCapability(self):
        self.assertTrue(self.device.hasCapability(PowerControl))
        self.assertTrue(self.device.hasCapability(AutostartControl))
        self.assertFalse(self.device.hasCapability(WavelengthControl))

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
