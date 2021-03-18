import time
import usb.core
import usb.util
import numpy as np
import matplotlib.pyplot as plt

from typing import NamedTuple

class Status(NamedTuple):
    pixelsLSB: int = None
    pixelsMSB: int = None
    integrationTimeMSB: int = None
    integrationTimeLSB: int = None
    lampEnable : bool = None
    triggerMode : int = None    
    requestSpectra: bool = None
    timerSwap: bool = None
    spectralDataReady : bool = None
    reserved0 = None
    reserved1 = None
    reserved2 = None
    reserved3 = None
    reserved4 = None
    reserved5 = None
    reserved6 = None

class USB2000:
    def __init__(self):
        self.idVendor = 0x2457
        self.idProduct = 0x1002
        self.device = usb.core.find(idVendor=self.idVendor, 
                                    idProduct=self.idProduct)        

        if self.device is None:
            raise ValueError('Device not found')

        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(0,0)]

        self.ep1Out = self.interface[0]
        self.ep1In = self.interface[1]
        self.ep7In = self.interface[3]
        self.initializeDevice()
        self.getCalibration()

    def initializeDevice(self):
        self.ep1Out.write(b'0x01')

    def setIntegrationTime(self, timeInMs):
        hi = timeInMs // 256
        lo = timeInMs % 256        
        self.ep1Out.write([0x02, lo, hi])

    def getCalibration(self):
        self.ep1Out.write([0x05, 0x01])        
        coefficentBytes = self.ep7In.read(size_or_buffer=17, timeout=1000)
        self.a0 = float(bytes(coefficentBytes[2:]).decode().rstrip('\x00'))
        self.ep1Out.write([0x05, 0x02])        
        coefficentBytes = self.ep7In.read(size_or_buffer=17, timeout=1000)
        self.a1 = float(bytes(coefficentBytes[2:]).decode().rstrip('\x00'))
        self.ep1Out.write([0x05, 0x03])        
        coefficentBytes = self.ep7In.read(size_or_buffer=17, timeout=1000)
        self.a2 = float(bytes(coefficentBytes[2:]).decode().rstrip('\x00'))
        self.ep1Out.write([0x05, 0x04])        
        coefficentBytes = self.ep7In.read(size_or_buffer=17, timeout=1000)
        self.a3 = float(bytes(coefficentBytes[2:]).decode().rstrip('\x00'))
        self.wavelength = [ self.a0 + self.a1*x + self.a2*x*x + self.a3*x*x*x 
                            for x in range(2048)]

    def requestSpectrum(self):
        self.ep1Out.write(b'\x09')
        while not self.isSpectrumRequested():
            plt.pause(0.001)

    def isSpectrumRequested(self):
        status = self.getStatus()
        return status[6] != 0

    def isSpectrumReady(self):
        status = self.getStatus()
        return status[8] != 0

    def getStatus(self):
        self.ep1Out.write(b'\xfe')
        return self.ep7In.read(size_or_buffer=16, timeout=1000)

    def getSpectrumData(self):
        spectrum = []
        for packet in range(32):
            bytesReadLow = self.ep1In.read(size_or_buffer=64, timeout=1000)
            bytesReadHi = self.ep1In.read(size_or_buffer=64, timeout=1000)
            
            spectrum.extend(np.array(bytesReadLow)+256*np.array(bytesReadHi))

        confirmation = self.ep1In.read(size_or_buffer=1, timeout=2)
        spectrum[0] = spectrum[1]

        assert(confirmation[0] == 0x69)
        return np.array(spectrum)

    def drawSpectrum(self):
        while True:
            self.requestSpectrum()
            while not self.isSpectrumReady():
                plt.pause(0.001)
            spectrum = self.getSpectrumData()

            plt.clf()
            plt.plot(self.wavelength, spectrum,'k')
            plt.draw()
            plt.pause(0.001)

if __name__ == "__main__":
    spectrometer = USB2000()
    spectrometer.setIntegrationTime(50)
    spectrometer.drawSpectrum()