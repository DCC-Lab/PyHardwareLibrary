import env
import os
import sys
import unittest
from enum import Enum

import hardwarelibrary.daq
import hardwarelibrary.powermeters
import hardwarelibrary.powerstrips
import hardwarelibrary.sources
import hardwarelibrary.spectrometers
from hardwarelibrary.capabilities import (
    Capability, allCapabilities, capabilityInterface,
    OnOffCapability, ShutterCapability, PowerCapability,
    AnalogInputCapability, AnalogOutputCapability, AnalogIOCapability,
    AnalogNotification, InputSource, OutletSwitchingCapability)
from hardwarelibrary.daq import DebugLabjackDevice, DebugSR830Device
from hardwarelibrary.physicaldevice import DeviceState, PhysicalDevice
from hardwarelibrary.powerstrips import DebugPwrUSBDevice
from hardwarelibrary.sources import DebugMatisseDevice, DebugMillenniaDevice
from notificationcenter import NotificationCenter


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
    # A family base that posts notifications names its enum the same way a
    # capability does, so the scheme is one rule across the whole library.
    readsThatKeepAWill = {"willGetSpectrum"}   # an acquisition, not a state read

    def familyBasesThatNotify(self):
        return [klass for klass in everySubclassOf(PhysicalDevice)
                if not isDeclaredInATestModule(klass)
                and "notification" in vars(klass)]

    def testFamilyBaseNotificationsAreNamedAfterTheirHooks(self):
        # Looser than the capability rule on purpose: a family base may group
        # several hooks under one name when they are one operation to an observer
        # (moveTo, moveBy and home all post willMove/didMove), so a member's stem
        # only has to begin a hook it stands for.
        for klass in self.familyBasesThatNotify():
            hookStems = [name[len("do"):] for name in vars(klass)
                         if name.startswith("do")]
            for memberName in klass.notification.__members__:
                self.assertRegex(memberName, r"^(will|did)")
                stem = memberName[len("will"):] if memberName.startswith("will") \
                    else memberName[len("did"):]
                self.assertTrue(any(hook.startswith(stem) for hook in hookStems),
                                "{0}.{1}".format(klass.notification.__name__, memberName))

    def testFamilyBaseReadsPostDidOnly(self):
        for klass in self.familyBasesThatNotify():
            for memberName in klass.notification.__members__:
                if not memberName.startswith("will"):
                    continue
                stem = memberName[len("will"):]
                isRead = stem.startswith("Get") or stem.startswith("Read")
                self.assertTrue(not isRead or memberName in self.readsThatKeepAWill,
                                "{0}.{1}".format(klass.notification.__name__, memberName))

    def testEveryFamilyBaseThatNotifiesIsCovered(self):
        # Guards the guard: if a family base stops declaring `notification`,
        # the two tests above would quietly check nothing.
        covered = {klass.__name__ for klass in self.familyBasesThatNotify()}
        self.assertTrue({"LinearMotionDevice", "RotationDevice", "PowerMeterDevice",
                         "Spectrometer"}.issubset(covered), covered)

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

    def validateReady(self, operation=None):
        """Stands in for a device that is open and ready."""
        pass

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


class TestStateGuard(unittest.TestCase):
    def setUp(self):
        self.laser = DebugMillenniaDevice()
        self.recorder = NotificationRecorder()
        self.recorder.observe(OnOffCapability.notification)

    def tearDown(self):
        self.recorder.stop()
        if self.laser.state == DeviceState.Ready:
            self.laser.shutdownDevice()

    def testAnOperationBeforeInitializationRaises(self):
        with self.assertRaises(PhysicalDevice.NotInitialized):
            self.laser.turnOn()

    def testTheErrorNamesTheOperationTheDeviceAndTheState(self):
        with self.assertRaises(PhysicalDevice.NotInitialized) as raised:
            self.laser.turnOn()
        message = str(raised.exception)
        self.assertIn("turnOn()", message)
        self.assertIn("DebugMillenniaEv25Device", message)
        self.assertIn("Unconfigured", message)

    def testNothingIsPostedWhenTheDeviceIsNotReady(self):
        # Not even a will: nothing was attempted and the hardware was never
        # touched, so an observer should hear nothing at all.
        with self.assertRaises(PhysicalDevice.NotInitialized):
            self.laser.turnOn()
        self.assertEqual(self.recorder.names(), [])

    def testAReadIsGuardedToo(self):
        with self.assertRaises(PhysicalDevice.NotInitialized):
            self.laser.isLaserOn()

    def testTheOperationRunsOnceTheDeviceIsReady(self):
        self.laser.initializeDevice()
        self.laser.turnOn()
        self.assertTrue(self.laser.isLaserOn())
        self.assertEqual(self.recorder.names(),
                         ["willTurnOn", "didTurnOn", "didGetOnOffState"])

    def testAShutdownDeviceIsGuardedAgain(self):
        self.laser.initializeDevice()
        self.laser.shutdownDevice()
        with self.assertRaises(PhysicalDevice.NotInitialized):
            self.laser.turnOn()

    def testWhatAnInstrumentSupportsCanBeAskedBeforeConnecting(self):
        # A UI populates its menus before the device is opened, so the methods
        # that only report capabilities of the model are exempt from the guard.
        lockin = DebugSR830Device()
        self.assertEqual(lockin.state, DeviceState.Unconfigured)
        self.assertIsNotNone(lockin.supportedSensitivities())
        self.assertIsNotNone(lockin.supportedTimeConstants())
        self.assertIsNotNone(lockin.supportedInputSources())
        self.assertIsNotNone(lockin.supportedTriggerSources())
        self.assertEqual(DebugPwrUSBDevice().outletCount, 3)

    def testEveryOtherOperationOfEveryCapabilityIsGuarded(self):
        # Walks the public API rather than naming methods, so a capability added
        # later cannot quietly escape the guard.
        exempt = {"supportedInputSources", "supportedSensitivities",
                  "supportedTimeConstants", "supportedTriggerSources",
                  "outletCount", "canTurnOn"}
        for capability in allCapabilities():
            for member in capabilityInterface(capability)["publicAPI"]:
                if member.name in exempt:
                    continue
                method = getattr(capability, member.name)
                self.assertTrue(hasattr(method, "__wrapped__"),
                                "{0}.{1} is not wrapped by @notifies".format(
                                    capability.__name__, member.name))


class TestArgumentValidation(unittest.TestCase):
    def setUp(self):
        self.daq = DebugLabjackDevice()
        self.daq.initializeDevice()
        self.strip = DebugPwrUSBDevice()
        self.strip.initializeDevice()
        self.recorder = NotificationRecorder()

    def tearDown(self):
        self.recorder.stop()
        self.daq.shutdownDevice()
        self.strip.shutdownDevice()

    def testARejectedCallPostsNothing(self):
        # The invariant the validate= hook buys: a will/did pair means the driver
        # really was invoked, so a refused call announces nothing at all.
        self.recorder.observe(AnalogNotification)
        with self.assertRaises(ValueError):
            self.daq.acquireWaveform([0], sampleRate=100, sampleCount=0)
        self.assertEqual(self.recorder.names(), [])

    def testAnEmptyChannelListIsRefusedClearly(self):
        # It used to fail inside the drain loop with "min() iterable argument is
        # empty", which named nothing the caller had written.
        with self.assertRaises(ValueError) as raised:
            self.daq.acquireWaveform([], sampleRate=100, sampleCount=10)
        self.assertIn("channels", str(raised.exception))

    def testASampleCountOfZeroNoLongerReturnsAnEmptyAcquisition(self):
        for sampleCount in (0, -5):
            with self.assertRaises(ValueError):
                self.daq.acquireWaveform([0], sampleRate=100, sampleCount=sampleCount)

    def testANegativeSampleRateIsRefused(self):
        with self.assertRaises(ValueError):
            self.daq.configureStream([0], sampleRate=-100)

    def testAnExternalClockMaySayItHasNoRate(self):
        self.daq.configureStream([0], sampleRate=None)   # accepted, means "not mine"

    def testALogicLevelMustBeOne(self):
        with self.assertRaises(TypeError):
            self.daq.setDigitalValue("yes", channel=4)
        self.daq.setDigitalValue(1, channel=4)           # 0 and 1 still work
        self.assertTrue(self.daq.getDigitalValue(4))

    def testAVoltageMustBeANumber(self):
        with self.assertRaises(TypeError):
            self.daq.setAnalogVoltage("2.5", channel=0)

    def testAnOutletMustBeOneTheStripHas(self):
        for outlet in (0, 4, 1.5):
            with self.assertRaises((ValueError, TypeError)):
                self.strip.turnOutletOn(outlet)
        self.strip.turnOutletOn(3)

    def testAWavelengthMustBeInTheRangeTheDriverReports(self):
        matisse = DebugMatisseDevice()
        matisse.initializeDevice()
        try:
            self.assertEqual(matisse.wavelengthRange(), (700.0, 1000.0))
            with self.assertRaises(ValueError) as raised:
                matisse.setWavelength(50.0)
            self.assertIn("700.0", str(raised.exception))
            matisse.setWavelength(780.0)
        finally:
            matisse.shutdownDevice()

    def testAnEnumArgumentAcceptsAnythingTheEnumAccepts(self):
        lockin = DebugSR830Device()
        lockin.initializeDevice()
        try:
            lockin.setInputSource("Differential")        # coerced for the driver
            self.assertEqual(lockin.getInputSource(), InputSource.Differential)
            with self.assertRaises(ValueError) as raised:
                lockin.setInputSource("Telepathy")
            self.assertIn("SingleEnded", str(raised.exception))
        finally:
            lockin.shutdownDevice()

    def testInstrumentLimitsStayWithTheDriver(self):
        # The capability checks the contract (a real number); the SR830's own
        # +/-10.5 V limit is the driver's business and still applies.
        lockin = DebugSR830Device()
        lockin.initializeDevice()
        try:
            with self.assertRaises(ValueError):
                lockin.setAnalogVoltage(50.0, channel=1)
        finally:
            lockin.shutdownDevice()


class _FailingAnalogDevice(AnalogIOCapability):
    """Every hook raises, so the failure path can be exercised."""

    class Failure(RuntimeError):
        pass

    def validateReady(self, operation=None):
        """Stands in for a device that is open and ready."""
        pass

    def doGetAnalogVoltage(self, channel):
        raise self.Failure("no hardware")

    def doSetAnalogVoltage(self, value, channel):
        raise self.Failure("no hardware")


class NotificationRecorder:
    """Collects every notification a capability posts, in order."""

    def __init__(self):
        self.received = []

    def observe(self, notificationEnum):
        for member in notificationEnum:
            NotificationCenter().add_observer(self, self.record, member)

    def record(self, notification):
        self.received.append(notification)

    def names(self):
        return [notification.name.name for notification in self.received]

    def stop(self):
        NotificationCenter().remove_observer(self)


class TestCapabilityNotifications(unittest.TestCase):
    def setUp(self):
        self.recorder = NotificationRecorder()

    def tearDown(self):
        self.recorder.stop()

    def testEveryCapabilityOwnsANotificationEnum(self):
        for capability in allCapabilities():
            self.assertTrue(issubclass(capability.notification, Enum), capability.__name__)

    def testNoEnumCarriesASeparateFailureMember(self):
        # A failure is reported through the operation's own did*, so a will* is
        # always followed by its did* and an observer never has to pair two
        # different members to know an operation ended.
        for capability in allCapabilities():
            self.assertNotIn("didFail", capability.notification.__members__,
                             capability.__name__)

    def testEveryHookHasItsDidNotification(self):
        for capability in allCapabilities():
            members = capability.notification.__members__
            for hook in capabilityInterface(capability)["hooks"]:
                stem = hook.name[len("do"):]
                self.assertIn("did" + stem, members,
                              "{0}.{1}".format(capability.__name__, hook.name))

    def testOnlyOperationsThatChangeTheInstrumentHaveAWillNotification(self):
        # A read posts did only: bracketing a value being read doubles the
        # traffic on the hot paths for no added information.
        for capability in allCapabilities():
            members = capability.notification.__members__
            for hook in capabilityInterface(capability)["hooks"]:
                stem = hook.name[len("do"):]
                isRead = hook.name.startswith("doGet") or hook.name.startswith("doRead")
                self.assertEqual("will" + stem not in members, isRead,
                                 "{0}.{1}".format(capability.__name__, hook.name))

    def testNoNotificationIsDefinedForAHookThatDoesNotExist(self):
        # An enum shared by a family of capabilities carries the members of every
        # hook in that family, so the stems are checked against their union.
        stemsByEnum = {}
        for capability in allCapabilities():
            stems = stemsByEnum.setdefault(capability.notification, set())
            stems.update(hook.name[len("do"):]
                         for hook in capabilityInterface(capability)["hooks"])
        for notificationEnum, hookStems in stemsByEnum.items():
            for memberName in notificationEnum.__members__:
                stem = memberName[len("will"):] if memberName.startswith("will") \
                    else memberName[len("did"):]
                self.assertIn(stem, hookStems,
                              "{0}.{1}".format(notificationEnum.__name__, memberName))

    def testCapabilitiesInOneInheritanceChainShareOneEnum(self):
        # Sharing is what makes the members interchangeable: a device mixing in
        # AnalogIOCapability posts the same member as one mixing in only
        # AnalogOutputCapability, so an observer registers once.
        for capability in allCapabilities():
            for other in allCapabilities():
                if capability is not other and issubclass(capability, other):
                    self.assertIs(capability.notification, other.notification,
                                  "{0} vs {1}".format(capability.__name__, other.__name__))

    def testAnActionPostsWillThenDidWithItsArgumentsAndResult(self):
        self.recorder.observe(AnalogNotification)
        device = _RecordingAnalogDevice()
        device.setAnalogVoltage(2.5, channel=1)
        self.assertEqual(self.recorder.names(),
                         ["willSetAnalogVoltage", "didSetAnalogVoltage"])
        willNotification, didNotification = self.recorder.received
        self.assertEqual(willNotification.user_info, {"value": 2.5, "channel": 1})
        self.assertEqual(didNotification.user_info,
                         {"value": 2.5, "channel": 1, "result": None, "error": None})

    def testAReadPostsDidOnly(self):
        self.recorder.observe(AnalogNotification)
        device = _RecordingAnalogDevice()
        device.getAnalogVoltage(3)
        self.assertEqual(self.recorder.names(), ["didGetAnalogVoltage"])
        self.assertEqual(self.recorder.received[0].user_info,
                         {"channel": 3, "result": 1.5, "error": None})

    def testTheNotifyingObjectIsTheDevice(self):
        self.recorder.observe(AnalogNotification)
        device = _RecordingAnalogDevice()
        device.getAnalogVoltage(0)
        self.assertIs(self.recorder.received[0].object, device)

    def testAFailingHookStillPostsDidCarryingTheErrorAndReRaisesUntouched(self):
        self.recorder.observe(AnalogNotification)
        device = _FailingAnalogDevice()
        with self.assertRaises(_FailingAnalogDevice.Failure):
            device.setAnalogVoltage(2.5, channel=1)
        self.assertEqual(self.recorder.names(),
                         ["willSetAnalogVoltage", "didSetAnalogVoltage"])
        payload = self.recorder.received[-1].user_info
        self.assertEqual(payload["value"], 2.5)
        self.assertEqual(payload["channel"], 1)
        self.assertIsNone(payload["result"])
        self.assertIsInstance(payload["error"], _FailingAnalogDevice.Failure)

    def testAFailingReadPostsItsDidWithTheError(self):
        self.recorder.observe(AnalogNotification)
        device = _FailingAnalogDevice()
        with self.assertRaises(_FailingAnalogDevice.Failure):
            device.getAnalogVoltage(0)
        self.assertEqual(self.recorder.names(), ["didGetAnalogVoltage"])
        self.assertIsInstance(self.recorder.received[0].user_info["error"],
                              _FailingAnalogDevice.Failure)

    def testAnObserverTellsSuccessFromFailureByTheErrorAlone(self):
        self.recorder.observe(AnalogNotification)
        _RecordingAnalogDevice().getAnalogVoltage(0)
        try:
            _FailingAnalogDevice().getAnalogVoltage(0)
        except _FailingAnalogDevice.Failure:
            pass
        succeeded, failed = self.recorder.received
        self.assertIs(succeeded.name, failed.name)
        self.assertIsNone(succeeded.user_info["error"])
        self.assertIsNotNone(failed.user_info["error"])

    def testDecoratedMethodsKeepTheirIdentity(self):
        # capabilityInterface and the docs read the public signature, so the
        # decorator must not replace it with (*args, **kwargs).
        interface = capabilityInterface(AnalogOutputCapability)
        member = interface["publicAPI"][0]
        self.assertEqual(member.name, "setAnalogVoltage")
        self.assertEqual(member.signature, "(value, channel)")
        self.assertEqual(AnalogOutputCapability.setAnalogVoltage.__doc__,
                         "Set the output on channel to value, in volts.")


if __name__ == "__main__":
    unittest.main()
