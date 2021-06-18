import struct
import enum
from os.path import exists
from typing import NamedTuple

class InvalidStartCode(Exception):
    def __init__(self, line):
        super().__init__("Invalid file format. Line must start with ':' but does not '{0}'".format(line))

class InvalidLineFormat(Exception):
    def __init__(self, line):
        super().__init__("Invalid line format: '{0}'".format(line))

class InvalidByteCount(Exception):
    def __init__(self, expectedByteCount, actualByteCount, line):
        super().__init__("Invalid file format. Expected byte count ({0}) does not match actual ({1}) on line '{2}'".format(expectedByteCount, actualByteCount, line))

class InvalidChecksum(Exception):
    def __init__(self, expectedChecksum, actualChecksum, line):
        super().__init__("Invalid checksum (expected: {0}, actual: {1}) for line: '{1}'".format(expectedChecksum, actualChecksum, line))

class NoEndOfFileMarker(Exception):
    def __init__(self, filepath):
        super().__init__("Invalid file format. No EOF record on last line '{0}'".format(filepath))

class FileNotFound(Exception):
    def __init__(self, filepath):
        super().__init__("File not found: '{0}'".format(filepath))

class RecordType(enum.Enum):
   data = 0
   endOfFile = 1
   extendedSegmentAddress = 2
   startSegmentAddress = 3
   extendedLinearAddress = 4
   startLinearAddress = 5

class Record(NamedTuple):
    address: int = 0
    byteCount: int = 0
    type: RecordType = None
    data:list = []
    checksum: int = None

class IntelHexReader:
    def __init__(self, filepath):
        if exists(filepath):
            self.filepath = filepath
            self.records = self.read()
        else:
            raise FileNotFound(filepath)

    def read(self) -> [Record]:
        records = []
        with open(self.filepath, 'r') as fileHandle:
            for line in fileHandle:
                while line[-1] == '\n' or line[-1] == '\r':
                    line  = line[0:-1]
                records.append(self.convertLineToRecord(line))

        # We know the last line must be the end of file
        # See record types: https://en.wikipedia.org/wiki/Intel_HEX
        if records[-1].type != RecordType.endOfFile:
            raise NoEndOfFileMarker(filepath)

        return records

    def convertLineToRecord(self, line) -> Record:
        """
        Convert a line from an IntelHex-formatted file to a Record structure.
        The record namedtuple has a byteCount, address, type, data, and
        checksum. The format is described here:
        https://en.wikipedia.org/wiki/Intel_HEX 

        The minimum length for a line is 11 characters (Data can be empty): 
        ":BBAAAATT[DD..]CC" 

        We note that 16-bit integers addresses are in big endian format, which
        forces us to use struct to decode because int("eeff",16) is always
        native and could be little-endian.

        When indexing data, allBytes[A:B] will start at A and will
        go up to, but exclude, B.
        """

        class Index(enum.IntEnum):
            byteCount = 0
            address = 1
            type = 3
            dataStart = 4
            checksum = -1

        if len(line) < 11:
            raise InvalidLineFormat(line)

        startCode = line[0]
        if startCode != ":":
            raise InvalidStartCode(line)

        hexLine = line[1:]
        allBytes = bytearray.fromhex(hexLine)

        (expectedByteCount) = allBytes[Index.byteCount]
        (address,) = struct.unpack('>H', allBytes[Index.address:Index.type])
        (type) = allBytes[Index.type]
        (data) = allBytes[Index.dataStart:Index.checksum] # up to, but excluding checksum
        (expectedChecksum) = allBytes[Index.checksum]

        actualByteCount = len(data)
        if actualByteCount != expectedByteCount:
            raise InvalidByteCount(expectedByteCount, actualByteCount, line)

        actualChecksum = self.checksum(allBytes[:Index.checksum]) # all bytes except checksum
        if actualChecksum != expectedChecksum:
            raise InvalidChecksum(actualChecksum, expectedChecksum, line)

        return Record(address = address,
                      byteCount = expectedByteCount,
                      type = RecordType(type), 
                      data = data,
                      checksum = expectedChecksum)

    def checksum(self, bytes) -> int :
        """
        The checksum validates there was no error in the data read. It is the
        least significant byte of the sum of the bytes then calculating the
        two's complement of the LSB (e.g., by inverting its bits
        with "exclusive or (^) 0xff" and adding one).
        """
        return ((sum(bytes) & 0xff) ^ 0xff) + 1
