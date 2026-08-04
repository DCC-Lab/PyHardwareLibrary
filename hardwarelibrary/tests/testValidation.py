import env
import unittest
from enum import Enum

from hardwarelibrary.validation import (
    requireAtLeast, requireBool, requireInteger, requireMember, requireNonEmpty,
    requirePositive, requireRealNumber, requireWithinRange)


class Colour(Enum):
    red = "red"
    green = "green"


class TestRequireRealNumber(unittest.TestCase):
    def testAcceptsIntsAndFloats(self):
        self.assertEqual(requireRealNumber(3, "value"), 3)
        self.assertEqual(requireRealNumber(-2.5, "value"), -2.5)

    def testRejectsBool(self):
        # bool is a subclass of int, so True would otherwise pass as 1.
        with self.assertRaises(TypeError):
            requireRealNumber(True, "value")

    def testRejectsStringsAndNone(self):
        for value in ("2.5", None, [1]):
            with self.assertRaises(TypeError):
                requireRealNumber(value, "value")

    def testMessageNamesTheParameterAndTheUnit(self):
        with self.assertRaises(TypeError) as raised:
            requireRealNumber("high", "power", "W")
        self.assertIn("power", str(raised.exception))
        self.assertIn("W", str(raised.exception))


class TestRequireInteger(unittest.TestCase):
    def testAcceptsInts(self):
        self.assertEqual(requireInteger(4, "outlet"), 4)

    def testRejectsFloatsAndBool(self):
        for value in (1.5, True):
            with self.assertRaises(TypeError):
                requireInteger(value, "outlet")


class TestRequireBool(unittest.TestCase):
    def testAcceptsBools(self):
        self.assertIs(requireBool(True, "isOn"), True)
        self.assertIs(requireBool(False, "isOn"), False)

    def testAcceptsZeroAndOneAsLogicLevels(self):
        self.assertIs(requireBool(1, "isOn"), True)
        self.assertIs(requireBool(0, "isOn"), False)

    def testRejectsAnythingElse(self):
        for value in ("yes", 2, None, 0.0):
            with self.assertRaises(TypeError):
                requireBool(value, "isOn")


class TestBounds(unittest.TestCase):
    def testRequireAtLeastIncludesTheBound(self):
        self.assertEqual(requireAtLeast(1, 1, "sampleCount"), 1)
        with self.assertRaises(ValueError):
            requireAtLeast(0, 1, "sampleCount")

    def testRequirePositiveExcludesZero(self):
        self.assertEqual(requirePositive(0.001, "seconds"), 0.001)
        for value in (0, -1):
            with self.assertRaises(ValueError):
                requirePositive(value, "seconds")

    def testRequireWithinRangeIncludesBothEnds(self):
        for value in (700.0, 850.0, 1000.0):
            self.assertEqual(requireWithinRange(value, (700.0, 1000.0), "wavelength"), value)
        for value in (699.9, 1000.1):
            with self.assertRaises(ValueError):
                requireWithinRange(value, (700.0, 1000.0), "wavelength")

    def testRequireWithinRangePassesWhenNoRangeIsAdvertised(self):
        # The check is only as good as what the driver reports.
        self.assertEqual(requireWithinRange(1e9, None, "wavelength"), 1e9)

    def testTheMessageCarriesTheBoundAndTheUnit(self):
        with self.assertRaises(ValueError) as raised:
            requireWithinRange(50.0, (700.0, 1000.0), "wavelength", "nm")
        message = str(raised.exception)
        self.assertIn("wavelength", message)
        self.assertIn("700.0", message)
        self.assertIn("1000.0", message)
        self.assertIn("nm", message)


class TestRequireNonEmpty(unittest.TestCase):
    def testAcceptsAPopulatedCollection(self):
        self.assertEqual(requireNonEmpty([0, 1], "channels"), [0, 1])

    def testRejectsAnEmptyOne(self):
        with self.assertRaises(ValueError):
            requireNonEmpty([], "channels")


class TestRequireMember(unittest.TestCase):
    def testAcceptsAMemberAndAnythingItIsBuiltFrom(self):
        self.assertIs(requireMember(Colour.red, Colour, "colour"), Colour.red)
        self.assertIs(requireMember("green", Colour, "colour"), Colour.green)

    def testRejectsAnythingElseNamingWhatWasAllowed(self):
        with self.assertRaises(ValueError) as raised:
            requireMember("purple", Colour, "colour")
        message = str(raised.exception)
        self.assertIn("colour", message)
        self.assertIn("red", message)
        self.assertIn("green", message)


if __name__ == "__main__":
    unittest.main()
