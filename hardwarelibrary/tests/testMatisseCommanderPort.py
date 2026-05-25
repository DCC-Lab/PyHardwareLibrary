import env
import unittest
import socketserver
import struct
import threading
import time

from hardwarelibrary.sources.matissecommanderport import MatisseCommanderPort, MatisseCommanderError


def frame(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


class MatisseCommanderHandler(socketserver.BaseRequestHandler):
    replies = {
        "IDN?": b':IDN: "Mock Matisse TS, S/N:00-00-00"',
        "MOTBI:POS?": b":MOTBI:POS 12345",
        "BAD?": b"!ERROR 1,undef_command",
        "MOTBI:HOME": b":MOTBI:HOME",
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
            command = payload.decode("utf-8")
            self.server.requests.append((header, command))
            reply = self.replies.get(command, b":" + payload)
            try:
                self.request.sendall(frame(reply))
            except OSError:
                return  # client closed without reading (e.g. on Close_Network_Connection)

    def recvExactly(self, n):
        data = bytearray()
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)


class TestMatisseCommanderPort(unittest.TestCase):
    def setUp(self):
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), MatisseCommanderHandler)
        self.server.requests = []
        self.server.daemon_threads = True
        self.serverThread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.serverThread.start()
        host, serverPort = self.server.server_address
        self.port = MatisseCommanderPort(host, serverPort, timeout=2.0)
        self.port.closeSettleDelay = 0.0  # no real hardware to wait for in tests
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

    def testReadStringStripsLeadingColonAndEchoedCommand(self):
        self.port.writeString("MOTBI:POS?")
        self.assertEqual(self.port.readString(), "12345")

    def testIdnReplyReturnsQuotedValue(self):
        self.port.writeString("IDN?")
        self.assertEqual(self.port.readString(), '"Mock Matisse TS, S/N:00-00-00"')

    def testEchoOnlyReplyReturnsEmptyValue(self):
        self.port.writeString("MOTBI:HOME")
        self.assertEqual(self.port.readString(), "")

    def testErrorReplyRaisesMatisseCommanderError(self):
        self.port.writeString("BAD?")
        with self.assertRaises(MatisseCommanderError):
            self.port.readString()

    def testErrorMessageIsPreserved(self):
        self.port.writeString("BAD?")
        try:
            self.port.readString()
            self.fail("expected MatisseCommanderError")
        except MatisseCommanderError as error:
            self.assertIn("undef_command", str(error))

    def testCloseSendsCloseNetworkConnection(self):
        self.port.close()
        self.assertFalse(self.port.isOpen)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if any(command == "Close_Network_Connection" for _, command in self.server.requests):
                break
            time.sleep(0.01)
        self.assertTrue(any(command == "Close_Network_Connection" for _, command in self.server.requests))


if __name__ == "__main__":
    unittest.main()
