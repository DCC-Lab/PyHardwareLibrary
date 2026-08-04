import env
import os
import sys
import unittest

import hardwarelibrary.daq
import hardwarelibrary.powermeters
import hardwarelibrary.powerstrips
import hardwarelibrary.sources
import hardwarelibrary.spectrometers
from hardwarelibrary.capabilities import (
    Capability, allCapabilities, capabilityInterface,
    OnOffCapability, ShutterCapability, PowerCapability,
    AnalogInputCapability, AnalogOutputCapability, AnalogIOCapability,
    OutletSwitchingCapability)
from hardwarelibrary.physicaldevice import PhysicalDevice


testsDirectory = os.path.dirname(os.path.abspath(__file__))


def everySubclassOf(aClass):
    """Yield every subclass of aClass, at any depth. A class reachable through
    more than one branch is yielded more than once."""
    for subclass in aClass.__subclasses__():
        yield subclass
        yield from everySubclassOf(subclass)


def isDeclaredInATestModule(aClass) -> bool:
    """True when aClass comes from a file in this directory. Matching on the
    file, not on the module name, because a test module is imported as either
    testFoo or hardwarelibrary.tests.testFoo depending on the runner."""
    module = sys.modules.get(aClass.__module__)
    fileName = getattr(module, "__file__", None)
    if fileName is None:
        return False
    return os.path.dirname(os.path.abspath(fileName)) == testsDirectory


class TestAllCapabilities(unittest.TestCase):
    def testEveryEntryIsACapability(self):
        for capability in allCapabilities():
            self.assertTrue(issubclass(capability, Capability), capability.__name__)

    def testMarkerBaseIsExcluded(self):
        self.assertNotIn(Capability, allCapabilities())

    def testNoDeviceIsReportedAsACapability(self):
        for capability in allCapabilities():
            self.assertFalse(issubclass(capability, PhysicalDevice), capability.__name__)

    def testEveryCapabilityCarriesTheCapabilitySuffix(self):
        for capability in allCapabilities():
            self.assertTrue(capability.__name__.endswith("Capability"), capability.__name__)

    def testCapabilitiesFromEveryFamilyAreListed(self):
        capabilities = allCapabilities()
        self.assertIn(OnOffCapability, capabilities)
        self.assertIn(AnalogIOCapability, capabilities)
        self.assertIn(OutletSwitchingCapability, capabilities)

    def testCapabilitiesThatOthersExtendAreStillListed(self):
        # AnalogIOCapability extends both of these, so a walk that only kept the
        # leaves of the class graph would drop them from the listing.
        capabilities = allCapabilities()
        self.assertIn(AnalogInputCapability, capabilities)
        self.assertIn(AnalogOutputCapability, capabilities)
        self.assertIn(AnalogIOCapability, capabilities)
        self.assertTrue(issubclass(AnalogIOCapability, AnalogInputCapability))
        self.assertTrue(issubclass(AnalogIOCapability, AnalogOutputCapability))

    def testDeclarationOrderIsPreserved(self):
        capabilities = allCapabilities()
        self.assertLess(capabilities.index(OnOffCapability), capabilities.index(ShutterCapability))
        self.assertLess(capabilities.index(ShutterCapability), capabilities.index(PowerCapability))
        self.assertLess(capabilities.index(PowerCapability), capabilities.index(AnalogInputCapability))

    def testNoDuplicateEntries(self):
        capabilities = allCapabilities()
        self.assertEqual(len(capabilities), len(set(capabilities)))

    def testNoCapabilityIsDeclaredOutsideTheCapabilitiesModule(self):
        # Walking the subclass graph finds capabilities wherever they are
        # declared, so comparing it against allCapabilities() is what enforces
        # the single-module rule. Test modules are exempt: they legitimately mix
        # capabilities into throwaway stand-ins for a driver.
        walked = {klass for klass in everySubclassOf(Capability)
                  if not issubclass(klass, PhysicalDevice)
                  and not isDeclaredInATestModule(klass)}
        self.assertEqual(walked, set(allCapabilities()))


class TestDeviceHookPattern(unittest.TestCase):
    def testNoDeviceDeclaresAnAbstractMethodOutsideItsDoHooks(self):
        # The same rule beyond the mixins: a family base (Spectrometer,
        # PowerMeterDevice, CameraDevice, ...) declares only do* hooks as
        # abstract, so its public API stays concrete and free to delegate.
        for klass in everySubclassOf(PhysicalDevice):
            if isDeclaredInATestModule(klass):
                continue
            for methodName in getattr(klass, "__abstractmethods__", ()):
                if methodName in vars(klass):
                    self.assertTrue(methodName.startswith("do"),
                                    "{0}.{1}".format(klass.__name__, methodName))


class _RecordingAnalogDevice(AnalogIOCapability):
    """Implements only the hooks, and records the calls the public methods make."""

    def __init__(self):
        self.calls = []

    def doGetAnalogVoltage(self, channel):
        self.calls.append(("doGetAnalogVoltage", channel))
        return 1.5

    def doSetAnalogVoltage(self, value, channel):
        self.calls.append(("doSetAnalogVoltage", value, channel))

    def doConfigureAnalogIO(self, parameters: dict):
        self.calls.append(("doConfigureAnalogIO", parameters))


class TestCapabilityInterface(unittest.TestCase):
    def namesOf(self, members):
        return [member.name for member in members]

    def testPublicAPIAndHooksAreSeparated(self):
        interface = capabilityInterface(OnOffCapability)
        self.assertEqual(set(self.namesOf(interface["publicAPI"])),
                         {"isLaserOn", "turnOn", "turnOff", "canTurnOn"})
        self.assertEqual(set(self.namesOf(interface["hooks"])),
                         {"doTurnOn", "doTurnOff", "doGetOnOffState"})

    def testNoPublicMethodIsMistakenForAHook(self):
        for capability in allCapabilities():
            interface = capabilityInterface(capability)
            for member in interface["publicAPI"]:
                self.assertFalse(member.name.startswith("do"), member.name)
            for member in interface["hooks"]:
                self.assertTrue(member.name.startswith("do"), member.name)

    def testPrivateMembersAreExcluded(self):
        for capability in allCapabilities():
            interface = capabilityInterface(capability)
            for member in interface["publicAPI"] + interface["hooks"]:
                self.assertFalse(member.name.startswith("_"), member.name)

    def testHooksAreReportedAsAbstract(self):
        interface = capabilityInterface(ShutterCapability)
        for member in interface["hooks"]:
            self.assertTrue(member.isAbstract, member.name)

    def testNoPublicMethodIsAbstract(self):
        # The library-wide pattern: a public method is concrete and delegates, so
        # it stays free to validate arguments and post notifications, and only the
        # do* hook a driver implements is abstract.
        for capability in allCapabilities():
            interface = capabilityInterface(capability)
            for member in interface["publicAPI"]:
                self.assertFalse(member.isAbstract,
                                 "{0}.{1}".format(capability.__name__, member.name))

    def testEveryCapabilityDeclaresAtLeastOneHook(self):
        for capability in allCapabilities():
            self.assertNotEqual(capabilityInterface(capability)["hooks"], [],
                                capability.__name__)

    def testPublicMethodsDelegateToTheirHook(self):
        device = _RecordingAnalogDevice()
        self.assertEqual(device.getAnalogVoltage(3), 1.5)
        device.setAnalogVoltage(2.5, channel=1)
        device.configureAnalogIO({"key": "value"})
        self.assertEqual(device.calls, [("doGetAnalogVoltage", 3),
                                        ("doSetAnalogVoltage", 2.5, 1),
                                        ("doConfigureAnalogIO", {"key": "value"})])

    def testSignatureOmitsSelf(self):
        interface = capabilityInterface(PowerCapability)
        signatures = {member.name: member.signature for member in interface["publicAPI"]}
        self.assertEqual(signatures["setPower"], "(power: float)")
        self.assertEqual(signatures["power"], "() -> float")

    def testPropertiesAreListedWithoutASignature(self):
        interface = capabilityInterface(OutletSwitchingCapability)
        outletCount = [member for member in interface["publicAPI"]
                       if member.name == "outletCount"]
        self.assertEqual(len(outletCount), 1)
        self.assertEqual(outletCount[0].signature, "")

    def testInheritedMembersAreLeftToTheCapabilityThatDeclaresThem(self):
        interface = capabilityInterface(AnalogIOCapability)
        self.assertNotIn("getAnalogVoltage", self.namesOf(interface["publicAPI"]))
        self.assertIn("getAnalogVoltage",
                      self.namesOf(capabilityInterface(AnalogInputCapability)["publicAPI"]))

    def testExtendsReportsTheCapabilitiesCombined(self):
        self.assertEqual(set(capabilityInterface(AnalogIOCapability)["extends"]),
                         {AnalogInputCapability, AnalogOutputCapability})
        self.assertEqual(capabilityInterface(OnOffCapability)["extends"], [])


if __name__ == "__main__":
    unittest.main()
