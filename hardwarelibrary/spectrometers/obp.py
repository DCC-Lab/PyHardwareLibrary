"""Ocean Binary Protocol (OBP) wire format used by modern Ocean Optics/Insight
spectrometers (QE Pro, STS, FX, HDX, ...). Frame layout, header fields, flag
bits, and error codes are taken from the QE Pro Data Sheet (see
manuals/QE-Pro-Data-Sheet.pdf, pages 21-29). Older models (USB2000, USB4000,
HR2000+) use a different protocol; see oceaninsight.py."""

import struct


class OBPError(RuntimeError):
    pass


class OBPMessage:
    startBytes = b'\xc1\xc0'
    footerBytes = b'\xc5\xc4\xc3\xc2'
    protocolVersion = 0x1100
    headerSize = 44
    checksumSize = 16
    footerSize = 4
    immediateDataSize = 16
    overheadSize = headerSize + checksumSize + footerSize

    flagResponseToRequest = 1 << 0
    flagAckResponse = 1 << 1
    flagAckRequested = 1 << 2
    flagNack = 1 << 3
    flagException = 1 << 4
    flagProtocolDeprecated = 1 << 5
    flagMessageDeprecated = 1 << 6

    errorMessages = {
        0: "Success",
        1: "Invalid or unsupported protocol",
        2: "Unknown message type",
        3: "Bad checksum",
        4: "Message too large",
        5: "Payload length does not match message type",
        6: "Payload data invalid",
        7: "Device not ready for given message type",
        8: "Unknown checksum type",
        9: "Device reset unexpectedly",
        10: "Too many buses",
        11: "Out of memory",
        12: "Requested information does not exist",
        13: "Internal error",
        14: "Message did not end properly",
        15: "Current scan interrupted",
    }

    _headerFormat = '<2sHHHII6sBB16sI'

    def __init__(self, messageType, immediateData=b'', payload=b'',
                 regarding=0, flags=None, errorNumber=0):
        if immediateData and payload:
            raise ValueError("Provide either immediateData or payload, not both")
        if len(immediateData) > self.immediateDataSize:
            raise ValueError(
                f"immediateData is {len(immediateData)} bytes; max is {self.immediateDataSize}")

        self.messageType = messageType
        self.immediateData = bytes(immediateData)
        self.payload = bytes(payload)
        self.regarding = regarding
        self.errorNumber = errorNumber
        self.flags = self.flagAckRequested if flags is None else flags

    def toBytes(self) -> bytes:
        immediateLen = len(self.immediateData)
        immediatePadded = self.immediateData + b'\x00' * (self.immediateDataSize - immediateLen)
        bytesRemaining = len(self.payload) + self.checksumSize + self.footerSize

        header = struct.pack(
            self._headerFormat,
            self.startBytes,
            self.protocolVersion,
            self.flags,
            self.errorNumber,
            self.messageType,
            self.regarding,
            b'\x00' * 6,
            0,
            immediateLen,
            immediatePadded,
            bytesRemaining,
        )
        return header + self.payload + b'\x00' * self.checksumSize + self.footerBytes

    @classmethod
    def fromBytes(cls, data: bytes) -> 'OBPMessage':
        if len(data) < cls.overheadSize:
            raise OBPError(
                f"Response too short: {len(data)} bytes, need at least {cls.overheadSize}")

        (start, protocol, flags, errorNumber, messageType, regarding,
         _reserved, _checksumType, immediateLen, immediateData, bytesRemaining
        ) = struct.unpack(cls._headerFormat, data[:cls.headerSize])

        if start != cls.startBytes:
            raise OBPError(f"Invalid start bytes: {start!r}, expected {cls.startBytes!r}")

        payloadLen = bytesRemaining - cls.checksumSize - cls.footerSize
        if payloadLen < 0:
            raise OBPError(f"Invalid bytes_remaining field: {bytesRemaining}")

        expectedLen = cls.headerSize + payloadLen + cls.checksumSize + cls.footerSize
        if len(data) < expectedLen:
            raise OBPError(f"Truncated message: got {len(data)} bytes, expected {expectedLen}")

        footer = data[expectedLen - cls.footerSize:expectedLen]
        if footer != cls.footerBytes:
            raise OBPError(f"Invalid footer: {footer!r}")

        payload = data[cls.headerSize:cls.headerSize + payloadLen]

        return cls(
            messageType=messageType,
            immediateData=immediateData[:immediateLen],
            payload=payload,
            regarding=regarding,
            flags=flags,
            errorNumber=errorNumber,
        )

    @property
    def isNack(self) -> bool:
        return bool(self.flags & self.flagNack)

    @property
    def isException(self) -> bool:
        return bool(self.flags & self.flagException)

    @property
    def data(self) -> bytes:
        return self.payload if self.payload else self.immediateData

    def raiseIfError(self):
        if self.isNack or self.isException or self.errorNumber != 0:
            reason = self.errorMessages.get(self.errorNumber, f"error code {self.errorNumber}")
            raise OBPError(
                f"Device error on message 0x{self.messageType:08x}: {reason}")

    def __repr__(self):
        return (f"OBPMessage(messageType=0x{self.messageType:08x}, "
                f"flags=0x{self.flags:04x}, errorNumber={self.errorNumber}, "
                f"data={self.data!r})")
