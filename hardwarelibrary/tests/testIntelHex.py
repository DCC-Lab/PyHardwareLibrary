import unittest
from hardwarelibrary.spectrometers.intelhexreader import *

class TestIntelHexReader(unittest.TestCase):
    hexFile = "../spectrometers/stellarnet.hex"
    def testCreateReader(self):
        reader = IntelHexReader(self.hexFile)
        self.assertIsNotNone(reader)

    def testGetLines(self):
        reader = IntelHexReader(self.hexFile)
        self.assertTrue(len(reader.records) > 0)

    def testEnums(self):
        self.assertIsNotNone(RecordType(1))

    def testLinesAreAllAddressTypeExceptLastLine(self):
        reader = IntelHexReader(self.hexFile)
        self.assertTrue(len(reader.records) > 0)
        for record in reader.records[:-1]:
            self.assertTrue(record.type == RecordType.data)

    def testLastLineEOF(self):
        reader = IntelHexReader(self.hexFile)
        self.assertTrue(len(reader.records) > 0)
        record = reader.records
        self.assertTrue(record[-1].type == RecordType.endOfFile)

    def testMissingFile(self):
        with self.assertRaises(FileNotFound):
            reader = IntelHexReader("I dont exist")        

    def testWrongFormatFile(self):
        with self.assertRaises(InvalidStartCode):
            reader = IntelHexReader("testIntelHex.py")        

    def testInvalidLine(self):
        reader = IntelHexReader(self.hexFile)        
        with self.assertRaises(InvalidStartCode):
            reader.convertLineToRecord("daniel cote")
        
    def testInvalidByteCount(self):
        reader = IntelHexReader(self.hexFile)
        #line =          ":0A0FA000000102020303040405052A"
        wrongByteCount = ":FF0FA000000102020303040405052A"
        
        with self.assertRaises(InvalidByteCount):
            reader.convertLineToRecord(wrongByteCount)

    def testInvalidChecksum(self):
        reader = IntelHexReader(self.hexFile)
        #line =         ":0A0FA000000102020303040405052A"
        wrongChecksum = ":0A0FA00000010202030304040505FF"
        
        with self.assertRaises(InvalidChecksum):
            reader.convertLineToRecord(wrongChecksum)

    def testEmptyLine(self):
        reader = IntelHexReader(self.hexFile)
        #line =    ":0A0FA000000102020303040405052A"
        tooShort = ""
        
        with self.assertRaises(InvalidLineFormat):
            reader.convertLineToRecord(tooShort)

    def testLineTooShort(self):
        reader = IntelHexReader(self.hexFile)
        #line =    ":0A0FA000000102020303040405052A"
        tooShort = ":0A0FA000"
        
        with self.assertRaises(InvalidLineFormat):
            reader.convertLineToRecord(tooShort)

    def testNewlineOrCarriageReturnOrBoth(self):
        reader = IntelHexReader(self.hexFile)
        line =      ":0A0FA000000102020303040405052A"
        lineCRNL =  ":0A0FA000000102020303040405052A\r\n"
        lineCR =    ":0A0FA000000102020303040405052A\r"
        lineNL =    ":0A0FA000000102020303040405052A\n"
        
        record = reader.convertLineToRecord(line)
        recordCRNL = reader.convertLineToRecord(lineCRNL)
        recordCR = reader.convertLineToRecord(lineCR)
        recordNL = reader.convertLineToRecord(lineNL)

        self.assertEqual(record, recordCRNL)
        self.assertEqual(record, recordCR)
        self.assertEqual(record, recordNL)

if __name__ == "__main__":
    unittest.main()