"""Ocean Insight QE Pro spectrometer driver.

Wire protocol is Ocean Binary Protocol (OBP); see obp.py and
manuals/QE-Pro-Data-Sheet.pdf for the full message catalog. The base class
:class:`Spectrometer` in base.py is the parent — we do not subclass
``oceaninsight.OISpectrometer`` because that file targets a different
(pre-OBP) protocol used by USB2000/USB4000/HR2000+.
"""

import struct
import time

import numpy as np
import usb.core
import usb.util

from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.spectrometers.base import Spectrometer, UnableToCommunicate
from hardwarelibrary.spectrometers.obp import OBPMessage


class QEPro(Spectrometer):
    classIdVendor = 0x2457
    classIdProduct = 0x4004

    activePixelCount = 1024
    totalPixelCount = 1044
    activePixelOffset = 10
    spectrumPayloadSize = 4208
    metadataSize = 32
    pixelMask = 0x3FFFF

    minIntegrationTimeMicroSec = 8_000
    maxIntegrationTimeMicroSec = 60 * 60 * 1_000_000

    usbReadTimeoutMs = 5_000
    usbWriteTimeoutMs = 2_000
    endpointAddress = 1

    msgReset = 0x00000000
    msgGetSerialNumber = 0x00000100
    msgAbortAcquisition = 0x00100000
    msgClearBuffer = 0x00100830
    msgAcquireIntoBuffer = 0x00100902
    msgGetBufferedSpectrum = 0x00100928
    msgGetIntegrationTime = 0x00110000
    msgSetIntegrationTime = 0x00110010
    msgGetTriggerMode = 0x00110100
    msgSetTriggerMode = 0x00110110
    msgGetWavelengthCoefficientCount = 0x00180100
    msgGetWavelengthCoefficient = 0x00180101

    def __init__(self, serialNumber=None, idProduct=None, idVendor=None):
        super().__init__(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.model = "QE Pro"
        self.wavelength = np.linspace(400, 1100, self.activePixelCount)
        self.integrationTime = self.minIntegrationTimeMicroSec
        self.usbDevice = None
        self._endpointIn = None
        self._endpointOut = None

    def doInitializeDevice(self):
        self.usbDevice = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.usbDevice is None:
            raise UnableToCommunicate(
                f"QE Pro {self.idVendor:#06x}:{self.idProduct:#06x} not found on USB bus")
        self.usbDevice.set_configuration()
        configuration = self.usbDevice.get_active_configuration()
        interface = configuration[(0, 0)]
        self._endpointOut = usb.util.find_descriptor(
            interface,
            custom_match=lambda e:
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
                and (e.bEndpointAddress & 0x0F) == self.endpointAddress,
        )
        self._endpointIn = usb.util.find_descriptor(
            interface,
            custom_match=lambda e:
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
                and (e.bEndpointAddress & 0x0F) == self.endpointAddress,
        )
        if self._endpointOut is None or self._endpointIn is None:
            raise UnableToCommunicate(
                f"QE Pro endpoint {self.endpointAddress} not found on active interface")
        self.wavelength = self._readWavelengthCalibration()

    def doShutdownDevice(self):
        if self.usbDevice is not None:
            usb.util.dispose_resources(self.usbDevice)
        self.usbDevice = None
        self._endpointIn = None
        self._endpointOut = None

    def sendOBP(self, messageType, immediateData=b'', payload=b'') -> OBPMessage:
        request = OBPMessage(
            messageType=messageType,
            immediateData=immediateData,
            payload=payload,
        )
        self._endpointOut.write(request.toBytes(), timeout=self.usbWriteTimeoutMs)
        response = OBPMessage.fromBytes(self._readMessage())
        response.raiseIfError()
        return response

    def _readMessage(self) -> bytes:
        buffer = bytearray()
        while len(buffer) < OBPMessage.headerSize:
            chunk = self._endpointIn.read(
                OBPMessage.headerSize - len(buffer),
                timeout=self.usbReadTimeoutMs,
            )
            buffer.extend(bytes(chunk))
        bytesRemaining = struct.unpack('<I', bytes(buffer[40:44]))[0]
        totalSize = OBPMessage.headerSize + bytesRemaining
        while len(buffer) < totalSize:
            chunk = self._endpointIn.read(
                totalSize - len(buffer),
                timeout=self.usbReadTimeoutMs,
            )
            buffer.extend(bytes(chunk))
        return bytes(buffer)

    def getSerialNumber(self) -> str:
        response = self.sendOBP(self.msgGetSerialNumber)
        return response.data.decode('ascii').rstrip('\x00')

    def getIntegrationTime(self) -> int:
        response = self.sendOBP(self.msgGetIntegrationTime)
        self.integrationTime = struct.unpack('<I', response.data[:4])[0]
        return self.integrationTime

    def setIntegrationTime(self, value):
        value = int(value)
        if not self.minIntegrationTimeMicroSec <= value <= self.maxIntegrationTimeMicroSec:
            raise ValueError(
                f"Integration time {value} µs out of range "
                f"[{self.minIntegrationTimeMicroSec}, {self.maxIntegrationTimeMicroSec}]")
        self.sendOBP(self.msgSetIntegrationTime, immediateData=struct.pack('<I', value))
        self.integrationTime = value

    def getSpectrum(self) -> np.ndarray:
        # QE Pro buffers spectra and the trigger machinery makes the simple
        # "request and read" sequence return stale data; the data sheet
        # (page 13) prescribes Abort -> Clear -> Acquire -> Get for each
        # software-triggered acquisition.
        self.sendOBP(self.msgAbortAcquisition)
        self.sendOBP(self.msgClearBuffer)
        self.sendOBP(self.msgAcquireIntoBuffer)
        response = self.sendOBP(self.msgGetBufferedSpectrum)
        return self._parseSpectrum(response.payload)

    def _parseSpectrum(self, payload: bytes) -> np.ndarray:
        if len(payload) != self.spectrumPayloadSize:
            raise UnableToCommunicate(
                f"Unexpected spectrum payload size: {len(payload)} (expected {self.spectrumPayloadSize})")
        pixelBytes = payload[self.metadataSize:]
        pixels = np.frombuffer(pixelBytes, dtype='<u4') & self.pixelMask
        return pixels[self.activePixelOffset:self.activePixelOffset + self.activePixelCount]

    def _readWavelengthCalibration(self) -> np.ndarray:
        countResponse = self.sendOBP(self.msgGetWavelengthCoefficientCount)
        count = countResponse.data[0]
        coefficients = []
        for index in range(count):
            response = self.sendOBP(
                self.msgGetWavelengthCoefficient,
                immediateData=bytes([index]),
            )
            coefficients.append(struct.unpack('<f', response.data[:4])[0])
        pixels = np.arange(self.activePixelCount, dtype=float)
        wavelength = np.zeros_like(pixels)
        for order, coefficient in enumerate(coefficients):
            wavelength += coefficient * (pixels ** order)
        return wavelength


class DebugQEPro(QEPro):
    classIdVendor = 0xFFFF
    classIdProduct = 0xFFF1

    def __init__(self, serialNumber='QEPDEBUG'):
        PhysicalDevice.__init__(
            self,
            serialNumber=serialNumber,
            idProduct=self.classIdProduct,
            idVendor=self.classIdVendor,
        )
        self.model = "DebugQEPro"
        self.wavelength = np.linspace(400, 1100, self.activePixelCount)
        self.integrationTime = 100_000
        self.usbDevice = None
        self._endpointIn = None
        self._endpointOut = None
        self._serial = serialNumber
        self._wavelengthCoefficients = [
            400.0,
            (1100.0 - 400.0) / self.activePixelCount,
            0.0,
            0.0,
        ]
        self._specCount = 0

    def doInitializeDevice(self):
        self.wavelength = self._readWavelengthCalibration()

    def doShutdownDevice(self):
        pass

    def sendOBP(self, messageType, immediateData=b'', payload=b'') -> OBPMessage:
        if messageType == self.msgGetSerialNumber:
            return OBPMessage(messageType=messageType,
                              payload=self._serial.encode('ascii'), flags=0)

        if messageType == self.msgGetIntegrationTime:
            return OBPMessage(messageType=messageType,
                              immediateData=struct.pack('<I', self.integrationTime), flags=0)

        if messageType == self.msgSetIntegrationTime:
            self.integrationTime = struct.unpack('<I', immediateData[:4])[0]
            return OBPMessage(messageType=messageType, flags=0)

        if messageType in (self.msgAbortAcquisition,
                           self.msgClearBuffer,
                           self.msgAcquireIntoBuffer,
                           self.msgReset):
            return OBPMessage(messageType=messageType, flags=0)

        if messageType == self.msgGetBufferedSpectrum:
            return OBPMessage(messageType=messageType,
                              payload=self._fakeSpectrumPayload(), flags=0)

        if messageType == self.msgGetWavelengthCoefficientCount:
            return OBPMessage(
                messageType=messageType,
                immediateData=bytes([len(self._wavelengthCoefficients)]),
                flags=0,
            )

        if messageType == self.msgGetWavelengthCoefficient:
            index = immediateData[0]
            return OBPMessage(
                messageType=messageType,
                immediateData=struct.pack('<f', self._wavelengthCoefficients[index]),
                flags=0,
            )

        raise NotImplementedError(
            f"DebugQEPro: no fake response for OBP message 0x{messageType:08x}")

    def _fakeSpectrumPayload(self) -> bytes:
        self._specCount += 1
        metadata = bytearray(self.metadataSize)
        struct.pack_into('<I', metadata, 0, self._specCount)
        struct.pack_into('<Q', metadata, 4, int(time.time() * 1_000_000))
        struct.pack_into('<I', metadata, 12, self.integrationTime)

        pixelIndices = np.arange(self.totalPixelCount, dtype=float)
        peakCenter = self.activePixelOffset + self.activePixelCount // 2
        spectrum = 50_000.0 * np.exp(-((pixelIndices - peakCenter) / 100.0) ** 2) + 1_000.0
        pixels = spectrum.astype('<u4').tobytes()
        return bytes(metadata) + pixels
