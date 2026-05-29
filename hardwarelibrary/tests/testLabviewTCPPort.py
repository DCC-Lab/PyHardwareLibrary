import env
import unittest
import socketserver
import struct
import threading

from hardwarelibrary.communication.labviewtcpport import LabviewTCPPort


def frame(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


class LabviewEchoHandler(socketserver.BaseRequestHandler):
    replies = {
        "WITH_COLON": ":SOME:CMD: value",   # a colon-prefixed reply must come back verbatim
        "UNICODE": "héllo",
    }

    def handle(self):
        while True:
            header = self.recvExactly(4)
            if header is None:
                return
            length = struct.unpack(">I", header)[0]
            payload = self.recvExactly(length)
            if payload is None:
                return
            request = payload.decode("utf-8")
            self.server.requests.append((header, request))
            reply = self.replies.get(request, request).encode("utf-8")  # default: echo
            try:
                self.request.sendall(frame(reply))
            except OSError:
                return

    def recvExactly(self, n):
        data = bytearray()
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)


class TestLabviewTCPPort(unittest.TestCase):
    def setUp(self):
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), LabviewEchoHandler)
        self.server.requests = []
        self.server.daemon_threads = True
        self.serverThread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.serverThread.start()
        host, serverPort = self.server.server_address
        self.port = LabviewTCPPort(host, serverPort, timeout=2.0)
        self.port.open()

    def tearDown(self):
        if self.port.isOpen:
            self.port.close()
        self.server.shutdown()
        self.server.server_close()

    def testWriteStringPrependsBigEndianLengthFrame(self):
        self.port.writeString("IDN?")
        self.port.readString()  # ensures the server has processed the request
        self.assertEqual(self.server.requests[-1], (struct.pack(">I", 4), "IDN?"))

    def testReadStringReturnsDecodedPayloadVerbatim(self):
        # The transport does no application parsing: a colon-prefixed reply comes
        # back exactly as received, not stripped.
        self.port.writeString("WITH_COLON")
        self.assertEqual(self.port.readString(), ":SOME:CMD: value")

    def testRoundTripsArbitraryString(self):
        self.port.writeString("MOTBI:WL 780.5000")
        self.assertEqual(self.port.readString(), "MOTBI:WL 780.5000")

    def testRoundTripsUtf8(self):
        self.port.writeString("UNICODE")
        self.assertEqual(self.port.readString(), "héllo")

    def testWriteStringReturnsPayloadLength(self):
        self.assertEqual(self.port.writeString("hello"), 5)
        self.port.readString()


if __name__ == "__main__":
    unittest.main()
