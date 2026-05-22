import env
import unittest
from struct import pack

from hardwarelibrary.communication.commands import (
    Command, TextCommand, DataCommand, DataEncoder, DataDecoder,
)


class TestCommandBase(unittest.TestCase):
    def testMatchesReturnsAlwaysFalse(self):
        cmd = Command(name="base")
        self.assertFalse(cmd.matches(b'anything'))
        cmd = Command(name="base")
        self.assertFalse(cmd.matches(b'base'))

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
        cmd = TextCommand(name="test", requestEncoder="SET {0} {1}\r")
        self.assertTrue(cmd.matches(b'SET foo 42\r'))

    def testAutoMatchPatternNoMatch(self):
        cmd = TextCommand(name="test", requestEncoder="SET {0} {1}\r")
        self.assertFalse(cmd.matches(b'GET foo\r'))

    def testExplicitMatchPattern(self):
        cmd = TextCommand(name="test", requestEncoder="s r{0}\r",
                          requestDecoder=r's r(0x[0-9a-fA-F]+)[\r\n]')
        self.assertTrue(cmd.matches(b's r0xFF\r'))
        self.assertTrue(cmd.matches(b's r0xFF\n'))

    def testExtractParams(self):
        cmd = TextCommand(name="test", requestEncoder="SET {0} {1}\r")
        params = cmd.extractParams(b'SET foo 42\r')
        self.assertEqual(params, ('foo', '42'))

    def testExtractParamsExplicitPattern(self):
        cmd = TextCommand(name="test", requestEncoder="g r{0}\n",
                          requestDecoder=r'g r(0x[0-9a-fA-F]+)[\r\n]')
        params = cmd.extractParams(b'g r0xc9\n')
        self.assertEqual(params, ('0xc9',))

    def testFormatResponseWithTemplate(self):
        cmd = TextCommand(name="test", requestEncoder="g r{0}\n",
                          replyEncoder="v {0}\r")
        result = cmd.formatResponse(("42",))
        self.assertEqual(result, bytearray(b'v 42\r'))

    def testFormatResponseStringFallback(self):
        cmd = TextCommand(name="test", requestEncoder="cmd\r")
        result = cmd.formatResponse("ok\r")
        self.assertEqual(result, bytearray(b'ok\r'))

    def testFormatResponseNone(self):
        cmd = TextCommand(name="test", requestEncoder="cmd\r")
        self.assertIsNone(cmd.formatResponse(None))

    def testNamedGroupExtractParams(self):
        cmd = TextCommand(name="test", requestEncoder="SET {key} {value}\r",
                          requestDecoder=r'SET (?P<key>\w+) (?P<value>-?\d+)\r')
        params = cmd.extractParams(b'SET foo 42\r')
        self.assertIsInstance(params, dict)
        self.assertEqual(params["key"], "foo")
        self.assertEqual(params["value"], "42")

    def testNamedGroupFormatResponse(self):
        cmd = TextCommand(name="test", requestEncoder="GET {key}\r",
                          requestDecoder=r'GET (?P<key>\w+)\r',
                          replyEncoder="VAL {value}\r")
        result = cmd.formatResponse({"value": "99"})
        self.assertEqual(result, bytearray(b'VAL 99\r'))

    def testEffectiveDecoderUsesExplicit(self):
        cmd = TextCommand(name="test", requestEncoder="SET {0}\r",
                          requestDecoder=r'SET (\w+)\r')
        self.assertEqual(cmd.effectiveDecoder, r'SET (\w+)\r')

    def testEffectiveDecoderUsesAuto(self):
        cmd = TextCommand(name="test", requestEncoder="SET {0}\r")
        self.assertEqual(cmd.effectiveDecoder, cmd._autoMatchPattern())


class TestDataCommandRecognition(unittest.TestCase):
    def testMatchesByPrefix(self):
        cmd = DataCommand(name="test", requestDecoder=DataDecoder(prefix=b'M'))
        self.assertTrue(cmd.matches(b'M\x01\x02'))

    def testMatchesCaseInsensitive(self):
        cmd = DataCommand(name="test", requestDecoder=DataDecoder(prefix=b'M'))
        self.assertTrue(cmd.matches(b'm\x01\x02'))

    def testPrefixDerivedFromData(self):
        cmd = DataCommand(name="test", data=b'C\r')
        self.assertTrue(cmd.matches(b'C'))
        self.assertTrue(cmd.matches(b'c'))

    def testNoMatchWrongPrefix(self):
        cmd = DataCommand(name="test", requestDecoder=DataDecoder(prefix=b'M'))
        self.assertFalse(cmd.matches(b'G\x01'))

    def testExtractParamsWithFormat(self):
        cmd = DataCommand(name="test",
                          requestDecoder=DataDecoder('<xl', prefix=b'S'))
        payload = pack('<cl', b'S', 42)
        params = cmd.extractParams(payload)
        self.assertEqual(params, (42,))

    def testExtractParamsNoFormat(self):
        cmd = DataCommand(name="test", requestDecoder=DataDecoder(prefix=b'G'))
        self.assertEqual(cmd.extractParams(b'G'), ())

    def testFormatResponseWithFormat(self):
        cmd = DataCommand(name="test",
                          requestDecoder=DataDecoder(prefix=b'G'),
                          replyEncoder=DataEncoder('<cl'))
        result = cmd.formatResponse((b'g', 99))
        expected = bytearray(pack('<cl', b'g', 99))
        self.assertEqual(result, expected)

    def testFormatResponseBytesFallback(self):
        cmd = DataCommand(name="test", requestDecoder=DataDecoder(prefix=b'H'))
        result = cmd.formatResponse(b'\r')
        self.assertEqual(result, bytearray(b'\r'))

    def testFormatResponseNone(self):
        cmd = DataCommand(name="test", requestDecoder=DataDecoder(prefix=b'H'))
        self.assertIsNone(cmd.formatResponse(None))

    def testEffectivePrefixExplicit(self):
        cmd = DataCommand(name="test", data=b'C\r',
                          requestDecoder=DataDecoder(prefix=b'X'))
        self.assertEqual(cmd.effectivePrefix, b'X')

    def testEffectivePrefixFromData(self):
        cmd = DataCommand(name="test", data=b'C\r')
        self.assertEqual(cmd.effectivePrefix, b'C')

    def testNoDataNoPrefix(self):
        cmd = DataCommand(name="test")
        self.assertIsNone(cmd.effectivePrefix)
        self.assertFalse(cmd.matches(b'anything'))

    def testNamedFieldExtractParams(self):
        cmd = DataCommand(name="test",
                          requestDecoder=DataDecoder('<xlllx', ('x', 'y', 'z'), prefix=b'M'))
        payload = pack('<clllc', b'M', 10, 20, 30, b'\r')
        params = cmd.extractParams(payload)
        self.assertIsInstance(params, dict)
        self.assertEqual(params['x'], 10)
        self.assertEqual(params['y'], 20)
        self.assertEqual(params['z'], 30)

    def testNamedFieldFormatResponse(self):
        cmd = DataCommand(name="test",
                          requestDecoder=DataDecoder(prefix=b'G'),
                          replyEncoder=DataEncoder('<cl', ('tag', 'value')))
        result = cmd.formatResponse({'tag': b'g', 'value': 99})
        expected = bytearray(pack('<cl', b'g', 99))
        self.assertEqual(result, expected)


class TestDataCommandSendSide(unittest.TestCase):
    def testBuildSendDataWithParams(self):
        cmd = DataCommand(name="MOVE",
            requestEncoder=DataEncoder('<clllc',
                                       ('header', 'x', 'y', 'z', 'terminator'),
                                       {'header': b'M', 'terminator': b'\r'}),
            requestDecoder=DataDecoder(prefix=b'M'))
        data = cmd.buildSendData(x=10, y=20, z=30)
        expected = pack('<clllc', b'M', 10, 20, 30, b'\r')
        self.assertEqual(data, expected)

    def testBuildSendDataFallbackToData(self):
        raw = pack('<cc', b'C', b'\r')
        cmd = DataCommand(name="GET", data=raw)
        self.assertEqual(cmd.buildSendData(), raw)

    def testBuildSendDataNoFormatNoData(self):
        cmd = DataCommand(name="EMPTY")
        self.assertIsNone(cmd.buildSendData())

    def testUnpackReplyWithMask(self):
        cmd = DataCommand(name="test", replyDecoder=DataDecoder('<lll'))
        replyBytes = pack('<lll', 100, 200, 300)
        result = cmd.unpackReply(replyBytes)
        self.assertEqual(result, (100, 200, 300))

    def testUnpackReplyNoMask(self):
        cmd = DataCommand(name="test")
        raw = b'\x01\x02\x03'
        self.assertEqual(cmd.unpackReply(raw), raw)


if __name__ == '__main__':
    unittest.main()
