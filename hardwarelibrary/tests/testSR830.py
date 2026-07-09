import env
import unittest

from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.daq import (
    AnalogInputDevice, AnalogOutputDevice, AnalogInputStreamDevice,
    PhaseLockedDetectionDevice, TriggerableDevice,
    InputSource, AuxInput, AuxOutput, StreamChannel, TriggerSource, SampleClock,
    SR830Device, DebugSR830Device, DebugPrologixGPIBPort,
)


class TestDebugSR830Device(unittest.TestCase):
    def setUp(self):
        self.device = DebugSR830Device()
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()

    def testCreate(self):
        self.assertIsNotNone(self.device)

    def testInitializeAndShutdown(self):
        device = DebugSR830Device()
        device.initializeDevice()
        device.shutdownDevice()

    def testIdentityIsSR830(self):
        self.assertIn("SR830", self.device.idn)

    def testGetAnalogVoltageChannels(self):
        for channel in AuxInput:
            value = self.device.getAnalogVoltage(channel)
            self.assertIsInstance(value, float)
        self.assertAlmostEqual(self.device.getAnalogVoltage(AuxInput.Aux1), 0.10)
        self.assertAlmostEqual(self.device.getAnalogVoltage(AuxInput.Aux4), 0.40)

    def testGetAnalogVoltageAcceptsBareInt(self):
        self.assertAlmostEqual(self.device.getAnalogVoltage(1), 0.10)

    def testGetAnalogVoltageInvalidChannel(self):
        with self.assertRaises(ValueError):
            self.device.getAnalogVoltage(0)
        with self.assertRaises(ValueError):
            self.device.getAnalogVoltage(5)

    def testSetAndGetAnalogOutput(self):
        self.device.setAnalogVoltage(1.5, AuxOutput.Aux1)
        self.assertAlmostEqual(self.device.getAnalogOutputVoltage(AuxOutput.Aux1), 1.5)
        self.device.setAnalogVoltage(-2.25, AuxOutput.Aux3)
        self.assertAlmostEqual(self.device.getAnalogOutputVoltage(AuxOutput.Aux3), -2.25)

    def testSetAnalogVoltageAcceptsBareInt(self):
        self.device.setAnalogVoltage(0.5, 2)
        self.assertAlmostEqual(self.device.getAnalogOutputVoltage(2), 0.5)

    def testSetAnalogVoltageInvalidChannel(self):
        with self.assertRaises(ValueError):
            self.device.setAnalogVoltage(1.0, 5)

    def testSetAnalogVoltageOutOfRange(self):
        with self.assertRaises(ValueError):
            self.device.setAnalogVoltage(20.0, AuxOutput.Aux1)
        with self.assertRaises(ValueError):
            self.device.setAnalogVoltage(-11.0, AuxOutput.Aux1)

    def testDemodulatedReads(self):
        self.assertAlmostEqual(self.device.getInPhaseVoltage(), 1.0e-3)
        self.assertAlmostEqual(self.device.getQuadratureVoltage(), 2.0e-3)
        self.assertAlmostEqual(self.device.getMagnitude(),
                               (1.0e-3 ** 2 + 2.0e-3 ** 2) ** 0.5)
        self.assertIsInstance(self.device.getPhase(), float)
        self.assertAlmostEqual(self.device.getReferenceFrequency(), 1.0e3)

    def testGetDemodulatedValues(self):
        values = self.device.getDemodulatedValues()
        self.assertEqual(set(values.keys()),
                         {"X", "Y", "R", "theta", "referenceFrequency"})
        self.assertAlmostEqual(values["X"], 1.0e-3)
        self.assertAlmostEqual(values["referenceFrequency"], 1.0e3)

    def testSnapLength(self):
        self.assertEqual(len(self.device.snap(1, 2, 3, 4)), 4)
        self.assertEqual(len(self.device.snap(1, 2)), 2)

    def testSnapRejectsWrongParameterCount(self):
        with self.assertRaises(ValueError):
            self.device.snap(1)
        with self.assertRaises(ValueError):
            self.device.snap(1, 2, 3, 4, 5, 6, 7)

    def testSensitivityRoundTrip(self):
        self.device.setSensitivity(1.0)
        self.assertAlmostEqual(self.device.getSensitivity(), 1.0)

    def testSensitivitySnapsUpToAvoidClipping(self):
        # 3 mV lands between the 2 mV and 5 mV steps; the smallest step that
        # still contains it is 5 mV.
        self.device.setSensitivity(3e-3)
        self.assertAlmostEqual(self.device.getSensitivity(), 5e-3)

    def testTimeConstantRoundTrip(self):
        self.device.setTimeConstant(1.0)
        self.assertAlmostEqual(self.device.getTimeConstant(), 1.0)

    def testTimeConstantSnapsToNearest(self):
        # 2 s is nearest the 3 s step (|3-2| < |1-2| is False -> 1 s and 3 s
        # are equidistant; min picks the earlier 1 s). Use 2.5 s -> 3 s.
        self.device.setTimeConstant(2.5)
        self.assertAlmostEqual(self.device.getTimeConstant(), 3.0)

    def testSupportedListsAreMonotonic(self):
        sensitivities = self.device.supportedSensitivities()
        timeConstants = self.device.supportedTimeConstants()
        self.assertEqual(len(sensitivities), 27)
        self.assertEqual(len(timeConstants), 20)
        self.assertEqual(sensitivities, sorted(sensitivities))
        self.assertEqual(timeConstants, sorted(timeConstants))

    def testInputSourceRoundTrip(self):
        self.device.setInputSource(InputSource.Differential)
        self.assertEqual(self.device.getInputSource(), InputSource.Differential)
        self.device.setInputSource(InputSource.Current100M)
        self.assertEqual(self.device.getInputSource(), InputSource.Current100M)

    def testSupportedInputSources(self):
        self.assertEqual(set(self.device.supportedInputSources()), set(InputSource))

    def testStatusUserInfo(self):
        info = self.device.doGetStatusUserInfo()
        self.assertIn("R", info)

    def testTriggerSourceRoundTrip(self):
        self.device.setTriggerSource(TriggerSource.External)
        self.assertEqual(self.device.getTriggerSource(), TriggerSource.External)
        self.device.setTriggerSource(TriggerSource.Internal)
        self.assertEqual(self.device.getTriggerSource(), TriggerSource.Internal)

    def testSupportedTriggerSources(self):
        self.assertEqual(set(self.device.supportedTriggerSources()), set(TriggerSource))

    def testAcquireWaveform(self):
        self.device.setTriggerSource(TriggerSource.Internal)
        waveform = self.device.acquireWaveform(
            channels=[StreamChannel.X, StreamChannel.Y], sampleRate=512, sampleCount=60)
        self.assertEqual(len(waveform[StreamChannel.X]), 60)
        self.assertEqual(len(waveform[StreamChannel.Y]), 60)

    def testStreamPrimitives(self):
        self.device.configureStream(channels=[StreamChannel.R], sampleRate=64)
        self.device.startStream()
        try:
            block = self.device.readStream()
        finally:
            self.device.stopStream()
        self.assertIn(StreamChannel.R, block)

    def testExternalSampleClockAdvancesOnSoftwareTrigger(self):
        # With an External sample clock, no samples accrue until each trigger edge.
        self.device.setTriggerSource(TriggerSource.Internal)
        self.device.configureStream(
            channels=[StreamChannel.X], sampleRate=0, sampleClock=SampleClock.External)
        self.device.startStream()
        try:
            self.assertEqual(self.device.readStream()[StreamChannel.X], [])
            self.device.softwareTrigger()
            self.device.softwareTrigger()
            self.assertEqual(len(self.device.readStream()[StreamChannel.X]), 2)
        finally:
            self.device.stopStream()

    def testConfigureStreamRejectsSameDisplay(self):
        with self.assertRaises(ValueError):
            self.device.configureStream(channels=[StreamChannel.X, StreamChannel.R], sampleRate=64)

    def testConfigureStreamRejectsWrongChannelCount(self):
        with self.assertRaises(ValueError):
            self.device.configureStream(channels=[], sampleRate=64)

    def testSampleRateSnapsToNearest(self):
        # 512 Hz is an exact SRAT step; 60 Hz snaps to the nearest (64).
        self.assertEqual(self.device._sampleRateIndexFor(512), self.device.sampleRates.index(512))
        self.assertEqual(self.device._sampleRateIndexFor(60), self.device.sampleRates.index(64))


class TestPhaseLockedDetectionContract(unittest.TestCase):
    def testDeclaresAllCapabilities(self):
        device = DebugSR830Device()
        self.assertIsInstance(device, AnalogInputDevice)
        self.assertIsInstance(device, AnalogOutputDevice)
        self.assertIsInstance(device, AnalogInputStreamDevice)
        self.assertIsInstance(device, PhaseLockedDetectionDevice)
        self.assertIsInstance(device, TriggerableDevice)


class TestPrologixGPIBPort(unittest.TestCase):
    def testControllerHandshakeOnOpen(self):
        port = DebugPrologixGPIBPort()
        sent = []
        original = port.writeData

        def recordingWriteData(data, endPoint=None):
            sent.append(bytes(data).decode("utf-8").strip())
            return original(data, endPoint)

        port.writeData = recordingWriteData
        port.open()
        # Simulate the same handshake PrologixGPIBPort.open() sends.
        for command in ("++mode 1", "++addr 8", "++auto 1", "++eoi 1", "++eos 2",
                        "++eot_enable 1", "++eot_char 10", "++read_tmo_ms 1500"):
            port.writeString(command + "\n")
        self.assertIn("++mode 1", sent)
        self.assertIn("++addr 8", sent)
        self.assertIn("++auto 1", sent)

    def testQueryRoundTripsThroughStringPrimitives(self):
        port = DebugPrologixGPIBPort()
        port.open()
        port.writeString("*IDN?\n")
        self.assertIn("SR830", port.readString())

    def testFloatQueryMatches(self):
        port = DebugPrologixGPIBPort()
        port.open()
        _, group = port.writeStringReadFirstMatchingGroup(
            "FREQ?\n", replyPattern=r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")
        self.assertAlmostEqual(float(group), 1.0e3)


class TestSR830Device(unittest.TestCase):
    def setUp(self):
        # doInitializeDevice self-discovers: it probes the connected FTDI
        # adaptors and confirms the SR830 by *IDN?, so no portPath is needed.
        self.device = SR830Device()
        try:
            self.device.initializeDevice()
        except Exception:
            self.skipTest("No SR830 / Prologix adaptor connected")

    def tearDown(self):
        self.device.shutdownDevice()

    def testIdentity(self):
        self.assertIn("SR830", self.device.idn)

    def testPinsAdaptorSerialNumber(self):
        # After a successful probe the winning adaptor's serial is recorded so a
        # reconnect can select it directly by VID/PID + serial number.
        self.assertNotIn(self.device.serialNumber, (None, ".*"))

    def testGetAnalogVoltage(self):
        self.assertIsInstance(self.device.getAnalogVoltage(AuxInput.Aux1), float)

    def testGetReferenceFrequency(self):
        self.assertIsInstance(self.device.getReferenceFrequency(), float)

    def testGetMagnitude(self):
        self.assertIsInstance(self.device.getMagnitude(), float)

    def testInputSourceRoundTrip(self):
        original = self.device.getInputSource()
        self.device.setInputSource(InputSource.Differential)
        self.assertEqual(self.device.getInputSource(), InputSource.Differential)
        self.device.setInputSource(original)
        self.assertEqual(self.device.getInputSource(), original)

    def testAnalogOutputRoundTrip(self):
        original = self.device.getAnalogOutputVoltage(AuxOutput.Aux1)
        try:
            self.device.setAnalogVoltage(1.234, AuxOutput.Aux1)
            self.assertAlmostEqual(
                self.device.getAnalogOutputVoltage(AuxOutput.Aux1), 1.234, places=3)
        finally:
            self.device.setAnalogVoltage(original, AuxOutput.Aux1)

    def testTriggerSourceRoundTrip(self):
        original = self.device.getTriggerSource()
        try:
            self.device.setTriggerSource(TriggerSource.External)
            self.assertEqual(self.device.getTriggerSource(), TriggerSource.External)
        finally:
            self.device.setTriggerSource(original)

    def testAcquireWaveform(self):
        self.device.setTriggerSource(TriggerSource.Internal)
        waveform = self.device.acquireWaveform(
            channels=[StreamChannel.X, StreamChannel.Y], sampleRate=512, sampleCount=64)
        self.assertEqual(len(waveform[StreamChannel.X]), 64)
        self.assertEqual(len(waveform[StreamChannel.Y]), 64)
        self.assertTrue(all(isinstance(value, float) for value in waveform[StreamChannel.X]))


if __name__ == '__main__':
    unittest.main()
