import env
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.powermeters import (
    FieldMasterDevice, DebugFieldMasterDevice, IntegraDevice,
)
from hardwarelibrary.devicemanager import DeviceManager
import hardwarelibrary.utils as utils


class TestGenericConverterFlag(unittest.TestCase):
    def testFieldMasterIsGeneric(self):
        self.assertTrue(FieldMasterDevice.usesGenericSerialConverter)

    def testDebugFieldMasterIsNotGeneric(self):
        self.assertFalse(DebugFieldMasterDevice.usesGenericSerialConverter)

    def testIntegraIsNotGeneric(self):
        self.assertFalse(IntegraDevice.usesGenericSerialConverter)

    def testBaseDefaultIsNotGeneric(self):
        self.assertFalse(PhysicalDevice.usesGenericSerialConverter)


class TestGenericConverterVidpids(unittest.TestCase):
    def testGenericExpandsToAllConverterVendors(self):
        expected = [(idVendor, None) for idVendor in SerialPort.genericSerialConverterVendors]
        self.assertEqual(FieldMasterDevice.vidpids(), expected)

    def testNonGenericKeepsSinglePair(self):
        self.assertEqual(IntegraDevice.vidpids(), [(0x1ad5, 0x0300)])

    def testDebugKeepsItsOwnPair(self):
        self.assertEqual(DebugFieldMasterDevice.vidpids(), [(0xFFFF, 0xFFF1)])


class TestGenericConverterCompatibility(unittest.TestCase):
    def testMatchesAnyGenericConverterVendorWithAnyProduct(self):
        # Same instrument behind FTDI, Prolific, or CP210x cables (different PIDs)
        self.assertTrue(FieldMasterDevice.isCompatibleWith("*", 0x6001, 0x0403))
        self.assertTrue(FieldMasterDevice.isCompatibleWith("*", 0x2303, 0x067b))
        self.assertTrue(FieldMasterDevice.isCompatibleWith("*", 0xEA60, 0x10c4))

    def testRejectsUnknownVendor(self):
        self.assertFalse(FieldMasterDevice.isCompatibleWith("*", 0x0001, 0x9999))

    def testNonGenericStillRequiresExactProduct(self):
        self.assertTrue(IntegraDevice.isCompatibleWith("*", 0x0300, 0x1ad5))
        self.assertFalse(IntegraDevice.isCompatibleWith("*", 0x9999, 0x1ad5))
        # No wildcard leak: a None product must not match a concrete pair.
        self.assertFalse(IntegraDevice.isCompatibleWith("*", None, 0x1ad5))

    def testDebugFieldMasterStillConstructs(self):
        device = DebugFieldMasterDevice()  # would raise if the flag broke its vidpids
        self.assertEqual(device.idVendor, 0xFFFF)
        self.assertEqual(device.idProduct, 0xFFF1)


class TestAutoDiscoveryGuard(unittest.TestCase):
    def testGenericClassesMatchButAreExcludedFromAutoDiscovery(self):
        candidates = utils.getCandidateDeviceClasses(PhysicalDevice, 0x0403, 0x6001)
        self.assertIn(FieldMasterDevice, candidates)  # it does match the FTDI cable

        discoverable = DeviceManager.candidateClassesForAutoDiscovery(0x0403, 0x6001)
        self.assertNotIn(FieldMasterDevice, discoverable)  # ...but is not auto-probed
        for aClass in discoverable:
            self.assertFalse(aClass.usesGenericSerialConverter)


if __name__ == "__main__":
    unittest.main()
