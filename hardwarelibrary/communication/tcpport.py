import socket
import select

from .communicationport import CommunicationPort, CommunicationReadTimeout


class UnableToOpenTCPPort(Exception):
    pass


class TCPPort(CommunicationPort):
    """A CommunicationPort over a raw TCP/IP socket (a byte stream).

    This is a generic transport: it knows nothing about any device's framing
    or protocol. readData/writeData move raw bytes, and readString uses the
    inherited terminator-based logic. A device whose wire format adds framing
    (for example a length-prefixed payload) should subclass this and override
    readData/writeData, leaving the connection handling here untouched.
    """

    def __init__(self, host, port, timeout=5.0):
        CommunicationPort.__init__(self)
        self.host = host
        self.port = port            # the TCP port number, not the connection
        self.timeout = timeout
        self.socket = None
        self.inputBuffer = bytearray()

    @property
    def isOpen(self):
        return self.socket is not None

    def open(self):
        if self.socket is not None:
            return

        try:
            self.socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as error:
            self.socket = None
            raise UnableToOpenTCPPort("Cannot connect to {0}:{1}: {2}".format(self.host, self.port, error))

        self.socket.settimeout(self.timeout)
        self.inputBuffer = bytearray()

    def close(self):
        if self.socket is not None:
            try:
                self.socket.close()
            finally:
                self.socket = None
                self.inputBuffer = bytearray()

    def bytesAvailable(self) -> int:
        with self.portLock:
            self.drainWithoutBlocking()
            return len(self.inputBuffer)

    def flush(self):
        with self.portLock:
            self.drainWithoutBlocking()
            self.inputBuffer = bytearray()

    def readData(self, length, endPoint=None) -> bytearray:
        with self.portLock:
            self.fillBufferToLength(length)
            data = self.inputBuffer[:length]
            del self.inputBuffer[:length]
        return bytearray(data)

    def writeData(self, data, endPoint=None) -> int:
        with self.portLock:
            self.socket.sendall(bytes(data))
        return len(data)

    def fillBufferToLength(self, length):
        # Block (up to the socket timeout) until the buffer holds length bytes.
        while len(self.inputBuffer) < length:
            try:
                chunk = self.socket.recv(4096)
            except socket.timeout:
                raise CommunicationReadTimeout(
                    "Timed out with {0} of {1} bytes".format(len(self.inputBuffer), length))
            if chunk == b"":
                raise CommunicationReadTimeout("Connection closed by peer")
            self.inputBuffer.extend(chunk)

    def drainWithoutBlocking(self):
        # Pull whatever has already arrived into the buffer without waiting.
        while True:
            readable, _, _ = select.select([self.socket], [], [], 0)
            if not readable:
                break
            chunk = self.socket.recv(4096)
            if chunk == b"":
                break
            self.inputBuffer.extend(chunk)
