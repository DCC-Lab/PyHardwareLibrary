import struct
import unittest

from hardwarelibrary.spectrometers.obp import OBPMessage, OBPError


class TestOBPMessage(unittest.TestCase):
    def testSetIntegrationTimeMatchesDataSheetExample(self):
        # QE Pro Data Sheet, page 26: Set Integration Time = 0x00110010
        # The example shows flags=0, regarding=0, integration time as 4 bytes
        # of immediate data (LSB first).
        integrationTime = 100_000
        message = OBPMessage(
            messageType=0x00110010,
            immediateData=struct.pack('<I', integrationTime),
            flags=0,
        )
        raw = message.toBytes()

        self.assertEqual(len(raw), 64)
        self.assertEqual(raw[0:2], b'\xc1\xc0')
        self.assertEqual(raw[2:4], b'\x00\x11')
        self.assertEqual(raw[4:6], b'\x00\x00')
        self.assertEqual(raw[6:8], b'\x00\x00')
        self.assertEqual(raw[8:12], b'\x10\x00\x11\x00')
        self.assertEqual(raw[12:16], b'\x00\x00\x00\x00')
        self.assertEqual(raw[16:22], b'\x00' * 6)
        self.assertEqual(raw[22], 0)
        self.assertEqual(raw[23], 4)
        self.assertEqual(raw[24:28], struct.pack('<I', integrationTime))
        self.assertEqual(raw[28:40], b'\x00' * 12)
        self.assertEqual(raw[40:44], b'\x14\x00\x00\x00')
        self.assertEqual(raw[44:60], b'\x00' * 16)
        self.assertEqual(raw[60:64], b'\xc5\xc4\xc3\xc2')

    def testGetBufferedSpectrumRequestMatchesDataSheetExample(self):
        # QE Pro Data Sheet, page 27: Get Buffered Spectra with Metadata = 0x00100928
        message = OBPMessage(messageType=0x00100928, flags=0)
        raw = message.toBytes()

        self.assertEqual(len(raw), 64)
        self.assertEqual(raw[0:2], b'\xc1\xc0')
        self.assertEqual(raw[8:12], b'\x28\x09\x10\x00')
        self.assertEqual(raw[23], 0)
        self.assertEqual(raw[40:44], b'\x14\x00\x00\x00')
        self.assertEqual(raw[60:64], b'\xc5\xc4\xc3\xc2')

    def testAckRequestedByDefault(self):
        message = OBPMessage(messageType=0x00000100)
        raw = message.toBytes()
        flags = int.from_bytes(raw[4:6], 'little')
        self.assertTrue(flags & OBPMessage.flagAckRequested)

    def testExplicitFlagsOverrideDefault(self):
        message = OBPMessage(messageType=0x00000100, flags=0)
        raw = message.toBytes()
        self.assertEqual(raw[4:6], b'\x00\x00')

    def testRoundTripEmptyPayload(self):
        original = OBPMessage(messageType=0x00100000, flags=0)
        parsed = OBPMessage.fromBytes(original.toBytes())
        self.assertEqual(parsed.messageType, 0x00100000)
        self.assertEqual(parsed.payload, b'')
        self.assertEqual(parsed.immediateData, b'')

    def testRoundTripWithImmediateData(self):
        original = OBPMessage(
            messageType=0x00110010,
            immediateData=struct.pack('<I', 50_000),
            regarding=0xDEADBEEF,
            flags=0,
        )
        parsed = OBPMessage.fromBytes(original.toBytes())
        self.assertEqual(parsed.messageType, 0x00110010)
        self.assertEqual(parsed.regarding, 0xDEADBEEF)
        self.assertEqual(struct.unpack('<I', parsed.immediateData)[0], 50_000)

    def testRoundTripWithPayload(self):
        payload = b'QEP01234'
        original = OBPMessage(messageType=0x00000100, payload=payload, flags=0)
        parsed = OBPMessage.fromBytes(original.toBytes())
        self.assertEqual(parsed.payload, payload)
        self.assertEqual(parsed.data, payload)

    def testDataPrefersPayloadOverImmediate(self):
        msg = OBPMessage(messageType=0, payload=b'\xaa\xbb', flags=0)
        self.assertEqual(msg.data, b'\xaa\xbb')

    def testDataFallsBackToImmediate(self):
        msg = OBPMessage(messageType=0, immediateData=b'\x42', flags=0)
        self.assertEqual(msg.data, b'\x42')

    def testParsesNackResponseAndRaises(self):
        nack = OBPMessage(
            messageType=0xDEADBEEF,
            flags=OBPMessage.flagResponseToRequest | OBPMessage.flagNack,
            errorNumber=2,
        )
        parsed = OBPMessage.fromBytes(nack.toBytes())
        self.assertTrue(parsed.isNack)
        self.assertEqual(parsed.errorNumber, 2)
        with self.assertRaises(OBPError):
            parsed.raiseIfError()

    def testRaiseIfErrorIsQuietOnSuccess(self):
        msg = OBPMessage(messageType=0x00000100, flags=OBPMessage.flagResponseToRequest)
        msg.raiseIfError()

    def testRejectsBadStartBytes(self):
        good = OBPMessage(messageType=0x00000080, flags=0).toBytes()
        bad = b'\x00\x00' + good[2:]
        with self.assertRaises(OBPError):
            OBPMessage.fromBytes(bad)

    def testRejectsBadFooter(self):
        good = OBPMessage(messageType=0x00000080, flags=0).toBytes()
        bad = good[:-4] + b'\x00\x00\x00\x00'
        with self.assertRaises(OBPError):
            OBPMessage.fromBytes(bad)

    def testRejectsTruncatedMessage(self):
        good = OBPMessage(messageType=0x00000080, flags=0).toBytes()
        with self.assertRaises(OBPError):
            OBPMessage.fromBytes(good[:32])

    def testRejectsImmediateAndPayloadTogether(self):
        with self.assertRaises(ValueError):
            OBPMessage(messageType=0, immediateData=b'\x01', payload=b'\x02')

    def testRejectsOversizedImmediateData(self):
        with self.assertRaises(ValueError):
            OBPMessage(messageType=0, immediateData=b'\x00' * 17)


if __name__ == '__main__':
    unittest.main()
