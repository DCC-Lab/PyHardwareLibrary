import struct

from .tcpport import TCPPort


class LabviewTCPPort(TCPPort):
    """A TCPPort that speaks LabVIEW's length-prefixed string framing.

    LabVIEW's TCP string primitives frame each string as a 4-byte big-endian
    length followed by exactly that many payload bytes, in both directions,
    with no terminator. A TCP server written in LabVIEW (such as Sirah's
    Matisse Commander) therefore expects and emits this framing.

    The packaging lives at the message layer (writeString/readString), not in
    readData/writeData: the protocol is length-delimited rather than
    terminator-delimited, and the inherited readString reads a byte at a time
    until a terminator that a length-prefixed stream never sends. readData and
    writeData stay as the raw byte-stream primitives. readString returns the
    decoded payload verbatim; any application-level reply grammar (command
    echoes, error markers) belongs to the device that owns the protocol, not
    to this transport.
    """

    lengthFormat = ">I"
    lengthSize = 4

    def writeString(self, string, endPoint=None) -> int:
        payload = bytearray(string, "utf-8")
        with self.portLock:
            frame = struct.pack(self.lengthFormat, len(payload)) + bytes(payload)
            super().writeData(frame, endPoint)
        return len(payload)

    def readString(self, endPoint=None) -> str:
        with self.portLock:
            header = bytes(super().readData(self.lengthSize, endPoint))
            length = struct.unpack(self.lengthFormat, header)[0]
            payload = bytes(super().readData(length, endPoint))
        return payload.decode("utf-8", errors="replace")
