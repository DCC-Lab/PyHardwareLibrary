import time
import usb.core
import usb.util
import numpy as np
import matplotlib.pyplot as plt
from struct import *
import csv

from typing import NamedTuple

class Status(NamedTuple):
    pixels : int = None
    integrationTime: int = None
    isLampEnabled : bool = None
    triggerMode : int = None    
    isSpectrumRequested: bool = None
    timerSwap: bool = None
    isSpectralDataReady : bool = None

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
        status = self.getStatus()
        self.a0 = float(self.getParameter(index=1))
        self.a1 = float(self.getParameter(index=2))
        self.a2 = float(self.getParameter(index=3))
        self.a3 = float(self.getParameter(index=4))
        self.wavelength = [ self.a0 + self.a1*x + self.a2*x*x + self.a3*x*x*x 
                            for x in range(status.pixels)]

    def getParameter(self, index):
        self.ep1Out.write([0x05, index])        
        parameters = self.ep7In.read(size_or_buffer=17, timeout=3000)
        return bytes(parameters[2:]).decode().rstrip('\x00')

    def requestSpectrum(self):
        self.ep1Out.write(b'\x09')
        while not self.isSpectrumRequested():
            plt.pause(0.001)

    def isSpectrumRequested(self):
        status = self.getStatus()
        return status.isSpectrumRequested

    def isSpectrumReady(self):
        status = self.getStatus()
        return status.isSpectralDataReady

    def getStatus(self):
        self.ep1Out.write(b'\xfe')
        status = self.ep7In.read(size_or_buffer=16, timeout=3000)
        statusList = unpack('>hh?B???xxxxxxx',status)
        return Status(*statusList)

    def getSpectrumData(self):
        spectrum = []
        for packet in range(32):
            bytesReadLow = self.ep1In.read(size_or_buffer=64, timeout=3000)
            bytesReadHi = self.ep1In.read(size_or_buffer=64, timeout=3000)
            
            spectrum.extend(np.array(bytesReadLow)+256*np.array(bytesReadHi))

        confirmation = self.ep1In.read(size_or_buffer=1, timeout=2)
        spectrum[0] = spectrum[1]

        assert(confirmation[0] == 0x69)
        return np.array(spectrum)

    def getSpectrum(self, integrationTime=None):
        if integrationTime is not None:
            self.setIntegrationTime(integrationTime)

        self.requestSpectrum()
        while not self.isSpectrumReady():
            plt.pause(0.001)
        return self.getSpectrumData()

    def saveSpectrum(self, filepath):
        spectrum = self.getSpectrum()
        with open(filepath, 'w', newline='\n') as csvfile:
            fileWrite = csv.writer(csvfile, delimiter=',')
            fileWrite.writerow(['Wavelength [nm]','Intensity [arb.u]'])
            for x,y in list(zip(self.wavelength, spectrum)):
                fileWrite.writerow(["{0:.2f}".format(x),y])

    def drawSpectrum(self):
        fig, ax = plt.subplots()
        while True:
            spectrum = self.getSpectrum()
            ax.cla()
            ax.set_ylim(0,4096)
            ax.plot(self.wavelength, spectrum, 'k')
            plt.draw()
            plt.pause(0.001)

if __name__ == "__main__":
    spectrometer = USB2000()
    spectrometer.setIntegrationTime(10)
    spectrometer.saveSpectrum('test.csv')
    spectrometer.drawSpectrum()