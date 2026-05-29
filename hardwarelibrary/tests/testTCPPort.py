import env
import unittest
import socket
import socketserver
import threading
import time

from hardwarelibrary.communication.tcpport import TCPPort, UnableToOpenTCPPort
from hardwarelibrary.communication.communicationport import CommunicationReadTimeout


class EchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        while True:
            data = self.request.recv(4096)
            if not data:
                break
            self.request.sendall(data)


class TestTCPPort(unittest.TestCase):
    def setUp(self):
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), EchoHandler)
        self.server.daemon_threads = True
        self.serverThread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.serverThread.start()
        self.host, self.serverPort = self.server.server_address
        self.port = TCPPort(self.host, self.serverPort, timeout=2.0)
        self.port.open()

    def tearDown(self):
        if self.port.isOpen:
            self.port.close()
        self.server.shutdown()
        self.server.server_close()

    def waitForReply(self, minBytes=1):
        deadline = time.time() + 2.0
        while self.port.bytesAvailable() < minBytes and time.time() < deadline:
            time.sleep(0.01)

    def testOpens(self):
        self.assertTrue(self.port.isOpen)

    def testCloses(self):
        self.port.close()
        self.assertFalse(self.port.isOpen)

    def testWriteReturnsByteCount(self):
        self.assertEqual(self.port.writeData(b"hello!"), 6)

    def testWriteAndReadData(self):
        self.port.writeData(b"hello!")
        self.assertEqual(bytes(self.port.readData(6)), b"hello!")

    def testReadString(self):
        self.port.writeString("ping\n")
        self.assertEqual(self.port.readString(), "ping\n")

    def testReadDataReassemblesExactLengths(self):
        self.port.writeData(b"abcdefghij")
        self.assertEqual(bytes(self.port.readData(4)), b"abcd")
        self.assertEqual(bytes(self.port.readData(6)), b"efghij")

    def testBytesAvailable(self):
        self.port.writeString("data\n")
        self.waitForReply(minBytes=5)
        self.assertGreaterEqual(self.port.bytesAvailable(), 5)

    def testFlushDiscardsPendingInput(self):
        self.port.writeString("garbage\n")
        self.waitForReply(minBytes=8)
        self.port.flush()
        self.assertEqual(self.port.bytesAvailable(), 0)

    def testReadTimeoutRaisesWhenNoData(self):
        shortPort = TCPPort(self.host, self.serverPort, timeout=0.3)
        shortPort.open()
        try:
            with self.assertRaises(CommunicationReadTimeout):
                shortPort.readData(1)  # nothing was sent; echo server stays silent
        finally:
            shortPort.close()


class TestTCPPortConnectionFailure(unittest.TestCase):
    def testOpenOnClosedPortRaises(self):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        freePort = probe.getsockname()[1]
        probe.close()  # release the port so nothing is listening

        port = TCPPort("127.0.0.1", freePort, timeout=1.0)
        with self.assertRaises(UnableToOpenTCPPort):
            port.open()


if __name__ == "__main__":
    unittest.main()
