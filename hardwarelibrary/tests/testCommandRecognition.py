import env
import unittest
from struct import pack

from hardwarelibrary.communication.commands import Command, TextCommand, DataCommand


class TestCommandBase(unittest.TestCase):
    def testMatchesReturnsFalse(self):
        cmd = Command(name="base")
        self.assertFalse(cmd.matches(b'anything'))

    def testExtractParamsReturnsEmpty(self):
        cmd = Command(name="base")
        self.assertEqual(cmd.extractParams(b'anything'), ())

    def testFormatResponseNone(self):
        cmd = Command(name="base")
        self.assertIsNone(cmd.formatResponse(None))

    def testFormatResponseBytes(self):
        cmd = Command(name="base")
        self.assertEqual(cmd.formatResponse(b'\x01\x02'), bytearray(b'\x01\x02'))

    def testFormatResponseString(self):
        cmd = Command(name="base")
        self.assertEqual(cmd.formatResponse("ok\r"), bytearray(b'ok\r'))


class TestTextCommandRecognition(unittest.TestCase):
    def testAutoMatchPattern(self):
        cmd = TextCommand(name="test", text="SET {0} {1}\r")
        self.assertTrue(cmd.matches(b'SET foo 42\r'))

    def testAutoMatchPatternNoMatch(self):
        cmd = TextCommand(name="test", text="SET {0} {1}\r")
        self.assertFalse(cmd.matches(b'GET foo\r'))

    def testExplicitMatchPattern(self):
        cmd = TextCommand(name="test", text="s r{0}\r",
                          matchPattern=r's r(0x[0-9a-fA-F]+)[\r\n]')
        self.assertTrue(cmd.matches(b's r0xFF\r'))
        self.assertTrue(cmd.matches(b's r0xFF\n'))

    def testExtractParams(self):
        cmd = TextCommand(name="test", text="SET {0} {1}\r")
        params = cmd.extractParams(b'SET foo 42\r')
        self.assertEqual(params, ('foo', '42'))

    def testExtractParamsExplicitPattern(self):
        cmd = TextCommand(name="test", text="g r{0}\n",
                          matchPattern=r'g r(0x[0-9a-fA-F]+)[\r\n]')
        params = cmd.extractParams(b'g r0xc9\n')
        self.assertEqual(params, ('0xc9',))

    def testFormatResponseWithTemplate(self):
        cmd = TextCommand(name="test", text="g r{0}\n",
                          responseTemplate="v {0}\r")
        result = cmd.formatResponse(("42",))
        self.assertEqual(result, bytearray(b'v 42\r'))

    def testFormatResponseStringFallback(self):
        cmd = TextCommand(name="test", text="cmd\r")
        result = cmd.formatResponse("ok\r")
        self.assertEqual(result, bytearray(b'ok\r'))

    def testFormatResponseNone(self):
        cmd = TextCommand(name="test", text="cmd\r")
        self.assertIsNone(cmd.formatResponse(None))

    def testNamedGroupExtractParams(self):
        cmd = TextCommand(name="test", text="SET {key} {value}\r",
                          matchPattern=r'SET (?P<key>\w+) (?P<value>-?\d+)\r')
        params = cmd.extractParams(b'SET foo 42\r')
        self.assertIsInstance(params, dict)
        self.assertEqual(params["key"], "foo")
        self.assertEqual(params["value"], "42")

    def testNamedGroupFormatResponse(self):
        cmd = TextCommand(name="test", text="GET {key}\r",
                          matchPattern=r'GET (?P<key>\w+)\r',
                          responseTemplate="VAL {value}\r")
        result = cmd.formatResponse({"value": "99"})
        self.assertEqual(result, bytearray(b'VAL 99\r'))

    def testEffectiveMatchPatternUsesExplicit(self):
        cmd = TextCommand(name="test", text="SET {0}\r",
                          matchPattern=r'SET (\w+)\r')
        self.assertEqual(cmd.effectiveMatchPattern, r'SET (\w+)\r')

    def testEffectiveMatchPatternUsesAuto(self):
        cmd = TextCommand(name="test", text="SET {0}\r")
        self.assertEqual(cmd.effectiveMatchPattern, cmd._autoMatchPattern)


class TestDataCommandRecognition(unittest.TestCase):
    def testMatchesByPrefix(self):
        cmd = DataCommand(name="test", prefix=b'M')
        self.assertTrue(cmd.matches(b'M\x01\x02'))

    def testMatchesCaseInsensitive(self):
        cmd = DataCommand(name="test", prefix=b'M')
        self.assertTrue(cmd.matches(b'm\x01\x02'))

    def testPrefixDerivedFromData(self):
        cmd = DataCommand(name="test", data=b'C\r')
        self.assertTrue(cmd.matches(b'C'))
        self.assertTrue(cmd.matches(b'c'))

    def testNoMatchWrongPrefix(self):
        cmd = DataCommand(name="test", prefix=b'M')
        self.assertFalse(cmd.matches(b'G\x01'))

    def testExtractParamsWithFormat(self):
        cmd = DataCommand(name="test", prefix=b'S', requestFormat='<xl')
        payload = pack('<cl', b'S', 42)
        params = cmd.extractParams(payload)
        self.assertEqual(params, (42,))

    def testExtractParamsNoFormat(self):
        cmd = DataCommand(name="test", prefix=b'G')
        self.assertEqual(cmd.extractParams(b'G'), ())

    def testFormatResponseWithFormat(self):
        cmd = DataCommand(name="test", prefix=b'G', responseFormat='<cl')
        result = cmd.formatResponse((b'g', 99))
        expected = bytearray(pack('<cl', b'g', 99))
        self.assertEqual(result, expected)

    def testFormatResponseBytesFallback(self):
        cmd = DataCommand(name="test", prefix=b'H')
        result = cmd.formatResponse(b'\r')
        self.assertEqual(result, bytearray(b'\r'))

    def testFormatResponseNone(self):
        cmd = DataCommand(name="test", prefix=b'H')
        self.assertIsNone(cmd.formatResponse(None))

    def testEffectivePrefixExplicit(self):
        cmd = DataCommand(name="test", data=b'C\r', prefix=b'X')
        self.assertEqual(cmd.effectivePrefix, b'X')

    def testEffectivePrefixFromData(self):
        cmd = DataCommand(name="test", data=b'C\r')
        self.assertEqual(cmd.effectivePrefix, b'C')

    def testNoDataNoPrefix(self):
        cmd = DataCommand(name="test")
        self.assertIsNone(cmd.effectivePrefix)
        self.assertFalse(cmd.matches(b'anything'))


if __name__ == '__main__':
    unittest.main()
