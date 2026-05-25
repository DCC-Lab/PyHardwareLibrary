import struct
import time

from ..communication.tcpport import TCPPort


class MatisseCommanderError(Exception):
    pass


class MatisseCommanderPort(TCPPort):
    """A TCPPort that speaks the Sirah Matisse Commander network framing.

    Matisse Commander does not delimit messages with a terminator: it frames
    each message as a 4-byte big-endian length followed by exactly that many
    payload bytes, in both directions. Replies echo the command behind a
    leading ':' (a query of MOTBI:POS returns ':MOTBI:POS 12345'), and errors
    come back as '!ERROR <code>,<message>'.

    Because the protocol is length-delimited rather than terminator-delimited,
    the framing lives at the message layer (writeString/readString), not in
    readData/writeData: the inherited readString reads one byte at a time until
    a terminator, which a length-prefixed stream never produces. readData and
    writeData stay as the raw byte-stream primitives, and readString returns the
    reply value with the ':' and echoed command stripped off, raising
    MatisseCommanderError when the device answers with '!ERROR'.
    """

    headerFormat = ">I"
    headerLength = 4
    closeCommand = "Close_Network_Connection"
    closeSettleDelay = 0.3

    def close(self):
        # Matisse Commander frees its (single) client slot only on receiving this
        # message; dropping the socket without it leaves the server holding a dead
        # connection and refusing the next client until it times out on its own.
        if self.isOpen:
            try:
                self.writeString(self.closeCommand)
                time.sleep(self.closeSettleDelay)
            except OSError:
                pass
        super().close()

    def writeString(self, string, endPoint=None) -> int:
        payload = bytearray(string, "utf-8")
        with self.portLock:
            frame = struct.pack(self.headerFormat, len(payload)) + bytes(payload)
            super().writeData(frame, endPoint)
        return len(payload)

    def readString(self, endPoint=None) -> str:
        with self.portLock:
            header = bytes(super().readData(self.headerLength, endPoint))
            length = struct.unpack(self.headerFormat, header)[0]
            payload = bytes(super().readData(length, endPoint))
        return self.parseReply(payload)

    def parseReply(self, payload) -> str:
        reply = bytes(payload).strip()
        if reply.upper().startswith(b"!ERROR"):
            message = reply[len(b"!ERROR"):].strip().decode("utf-8", errors="replace")
            raise MatisseCommanderError(message)
        if reply.startswith(b":"):
            parts = reply.split(maxsplit=1)
            reply = parts[1] if len(parts) > 1 else b""
        return reply.decode("utf-8", errors="replace")
