import time
import usb.core
import usb.util
import numpy as np
import matplotlib.pyplot as plt

class USB2000:
    def __init__(self):
        self.idVendor = 0x2457
        self.idProduct = 0x1002
        self.device = usb.core.find(idVendor=self.idVendor, 
                                    idProduct=self.idProduct)        

        if self.device is None:
            raise ValueError('Device not found')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        self.device.set_configuration(1)
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(0,0)]

        self.ep1Out = self.interface[0]
        self.ep1In = self.interface[1]
        self.ep7In = self.interface[3]
        self.initializeDevice()

    def initializeDevice(self):
        self.ep1Out.write(b'0x01')
        # self.getSpectrumData()
        
    def setIntegrationTime(self, timeInMs):
        hi = timeInMs // 256
        lo = timeInMs % 256        
        self.ep1Out.write([0x02, lo, hi])

    def requestSpectrum(self):
        self.ep1Out.write(b'\x09')
        while not self.isSpectrumRequested():
            plt.pause(0.001)

    def isSpectrumRequested(self):
        self.ep1Out.write(b'\xfe')
        status = self.ep7In.read(size_or_buffer=16, timeout=1000)
        requested = status[6]
        return requested != 0

    def isSpectrumReady(self):
        self.ep1Out.write(b'\xfe')
        status = self.ep7In.read(size_or_buffer=16, timeout=1000)
        ready = status[8]
        return ready != 0

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
            plt.plot(spectrum,'k')
            plt.draw()
            plt.pause(0.001)

if __name__ == "__main__":
    spectrometer = USB2000()
    spectrometer.setIntegrationTime(100)
    spectrometer.drawSpectrum()