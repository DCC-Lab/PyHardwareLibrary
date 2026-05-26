import env
import unittest
import socketserver
import struct
import threading
import time

from hardwarelibrary.sources.matisse import MatisseDevice, DebugMatisseDevice, MatisseCommanderError
from hardwarelibrary.sources.capabilities import WavelengthControl
from hardwarelibrary.physicaldevice import PhysicalDevice, DeviceState

MATISSE_HOST = "172.16.8.57"
MATISSE_PORT = 30000


def labviewFrame(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


class MatisseMockHandler(socketserver.BaseRequestHandler):
    """A local stand-in for Matisse Commander: LabVIEW framing + Matisse grammar."""

    def handle(self):
        while True:
            header = self.recvExactly(4)
            if header is None:
                return
            length = struct.unpack(">I", header)[0]
            payload = self.recvExactly(length)
            if payload is None:
                return
            command = payload.decode("utf-8").strip()
            self.server.requests.append(command)
            reply = self.replyFor(command)
            if reply is not None:
                try:
                    self.request.sendall(labviewFrame(reply.encode("utf-8")))
                except OSError:
                    return

    def replyFor(self, command):
        if command == "Close_Network_Connection":
            return None  # server-only command, no device reply (and the client does not read one)
        if command == "IDN?":
            return ':IDN: "Matisse Mock, S/N:00-00-00"'
        if command.startswith("BAD"):
            return '!ERROR 1,"general syntax error"'
        if command.endswith("?"):
            base = command[:-1]
            return ":{0}: {1}".format(base, self.server.values.get(base, "0"))
        parts = command.split(maxsplit=1)
        if len(parts) == 2:
            self.server.values[parts[0]] = parts[1]
        return "OK"

    def recvExactly(self, n):
        data = bytearray()
        while len(data) < n:
            chunk = self.request.recv(n - len(data))
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)


class TestDebugMatisseDevice(unittest.TestCase):
    def setUp(self):
        self.matisse = DebugMatisseDevice()
        self.matisse.initializeDevice()

    def tearDown(self):
        self.matisse.shutdownDevice()

    def testIsPhysicalDeviceWithWavelengthCapability(self):
        self.assertIsInstance(self.matisse, PhysicalDevice)
        self.assertIsInstance(self.matisse, WavelengthControl)

    def testInitializeReadsIdn(self):
        self.assertEqual(self.matisse.state, DeviceState.Ready)
        self.assertIn("Matisse", self.matisse.idn)

    def testBifiWavelengthRoundTrip(self):
        self.matisse.setBifiWavelength(782.5)
        self.assertAlmostEqual(self.matisse.bifiWavelength(), 782.5, places=4)

    def testBifiPositionRoundTrip(self):
        self.matisse.setBifiPosition(123456)
        self.assertEqual(self.matisse.bifiPosition(), 123456)

    def testWavelengthCapabilityDrivesBifi(self):
        self.matisse.setWavelength(805.0)
        self.assertAlmostEqual(self.matisse.wavelength(), 805.0, places=4)
        self.assertAlmostEqual(self.matisse.bifiWavelength(), 805.0, places=4)

    def testWavelengthRangeIsTheConfiguredRange(self):
        self.assertEqual(self.matisse.wavelengthRange(), (700.0, 1000.0))

    def testThinEtalonLockToggles(self):
        self.assertFalse(self.matisse.thinEtalonLockIsOn())
        self.matisse.setThinEtalonLock(True)
        self.assertTrue(self.matisse.thinEtalonLockIsOn())
        self.matisse.setThinEtalonLock(False)
        self.assertFalse(self.matisse.thinEtalonLockIsOn())

    def testThinEtalonErrorSignalFallsBackWhenCommandAbsent(self):
        # fw 1.20 has no TE:CNTRERR; value is setpoint - reflex/resonator.
        expected = 0.5 - 0.42 / 0.45
        self.assertAlmostEqual(self.matisse.thinEtalonErrorSignal(), expected, places=6)

    def testPiezoEtalonAmplitudeRoundTrip(self):
        self.matisse.setPiezoEtalonAmplitude(0.0123)
        self.assertAlmostEqual(self.matisse.piezoEtalonAmplitude(), 0.0123, places=6)

    def testPiezoEtalonPhaseRoundTrip(self):
        self.matisse.setPiezoEtalonPhase(42)
        self.assertEqual(self.matisse.piezoEtalonPhase(), 42)

    def testSlowPiezoSetpointRoundTrip(self):
        self.matisse.setSlowPiezoSetpoint(0.321)
        self.assertAlmostEqual(self.matisse.slowPiezoSetpoint(), 0.321, places=6)

    def testFastPiezoLockReadsBoolean(self):
        self.assertFalse(self.matisse.fastPiezoIsLocked())

    def testScanLimitsRoundTrip(self):
        self.matisse.setScanLowerLimit(0.2)
        self.matisse.setScanUpperLimit(0.8)
        self.assertAlmostEqual(self.matisse.scanLowerLimit(), 0.2, places=6)
        self.assertAlmostEqual(self.matisse.scanUpperLimit(), 0.8, places=6)

    def testScanDeviceRoundTrip(self):
        self.matisse.setScanDevice(2)
        self.assertEqual(self.matisse.scanDevice(), 2)

    def testBifiNotMovingWhenIdle(self):
        self.assertFalse(self.matisse.bifiIsMoving())

    def testWaitTimesOutWhileMoving(self):
        self.matisse.registers["MOTBI:STA"] = str(MatisseDevice.movingStatusBit | 0x02)
        self.assertTrue(self.matisse.bifiIsMoving())
        with self.assertRaises(MatisseDevice.MotionTimeout):
            self.matisse.waitForBifi(timeout=0.1)

    def testParseReplyStripsColonAndEchoedCommand(self):
        self.assertEqual(self.matisse.parseReply(":MOTBI:POS: 12345"), "12345")

    def testParseReplyKeepsQuotedIdnValue(self):
        self.assertEqual(self.matisse.parseReply(':IDN: "Matisse TS"'), '"Matisse TS"')

    def testParseReplyEchoOnlyReturnsEmpty(self):
        self.assertEqual(self.matisse.parseReply(":MOTBI:HOME:"), "")

    def testParseReplyPassesPlainReplyThrough(self):
        self.assertEqual(self.matisse.parseReply("OK"), "OK")

    def testParseReplyRaisesAndPreservesErrorMessage(self):
        try:
            self.matisse.parseReply('!ERROR 1,"general syntax error"')
            self.fail("expected MatisseCommanderError")
        except MatisseCommanderError as error:
            self.assertIn("general syntax error", str(error))


class TestMatisseDeviceOverMockServer(unittest.TestCase):
    def setUp(self):
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), MatisseMockHandler)
        self.server.requests = []
        self.server.values = {"MOTBI:WL": "780.5", "MOTBI:STA": "2"}
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        host, serverPort = self.server.server_address
        self.matisse = MatisseDevice(host, serverPort)
        self.matisse.closeSettleDelay = 0.0
        self.matisse.initializeDevice()

    def tearDown(self):
        if self.matisse.state == DeviceState.Ready:
            self.matisse.shutdownDevice()
        self.server.shutdown()
        self.server.server_close()

    def testInitializeReadsIdnOverRealTransport(self):
        self.assertEqual(self.matisse.idn, '"Matisse Mock, S/N:00-00-00"')

    def testQueryParsesValueFromFramedReply(self):
        self.assertAlmostEqual(self.matisse.bifiWavelength(), 780.5, places=4)

    def testSetSendsCommandAndConsumesOk(self):
        self.matisse.setBifiWavelength(790.0, wait=False)
        self.assertIn("MOTBI:WL 790.0000", self.server.requests)
        self.assertAlmostEqual(self.matisse.bifiWavelength(), 790.0, places=4)

    def testErrorReplyRaisesOverRealTransport(self):
        with self.assertRaises(MatisseCommanderError):
            self.matisse.queryString("BAD?")

    def testShutdownSendsCloseNetworkConnection(self):
        self.matisse.shutdownDevice()
        deadline = time.time() + 2.0
        while "Close_Network_Connection" not in self.server.requests and time.time() < deadline:
            time.sleep(0.01)
        self.assertIn("Close_Network_Connection", self.server.requests)


class TestMatisseDevice(unittest.TestCase):
    def setUp(self):
        self.matisse = MatisseDevice(MATISSE_HOST, MATISSE_PORT)
        try:
            self.matisse.initializeDevice()
        except PhysicalDevice.UnableToInitialize:
            self.skipTest("No Matisse Commander reachable at {0}:{1}".format(MATISSE_HOST, MATISSE_PORT))

    def tearDown(self):
        if self.matisse.state == DeviceState.Ready:
            self.matisse.shutdownDevice()

    def testIdentifiesAsMatisse(self):
        self.assertIn("Matisse", self.matisse.idn)

    def testReadsBifiWavelengthInRange(self):
        wavelength = self.matisse.bifiWavelength()
        self.assertGreater(wavelength, 600.0)
        self.assertLess(wavelength, 1100.0)

    def testReadsEveryTuningElementWithoutError(self):
        self.matisse.bifiPosition()
        self.matisse.thinEtalonPosition()
        self.matisse.thinEtalonReflexPower()
        self.matisse.thinEtalonErrorSignal()
        self.matisse.piezoEtalonBaseline()
        self.matisse.slowPiezoValue()
        self.matisse.fastPiezoValue()
        self.matisse.scanValue()


if __name__ == "__main__":
    unittest.main()
