import time
import usb.core
import usb.util
import numpy as np
import matplotlib.pyplot as plt

class USB2000:
    idVendor = 0x2457
    idProduct = 0x1002

    cmdInitialize = b'0x01'
    cmdSetIntegationTime = b'0x02'
    cmdSetStrobeEnable = b'0x03'
    cmdQueryInformation = b'0x05'
    cmdWriteInformation = b'0x06'
    cmdWriteSerialNumber = b'0x07'
    cmdGetSerialNumber = b'0x08'
    cmdRequestSpectra = b'0x09'
    cmdSetTriggerMode = b'0x0a'
    cmdQueryNumberPluginsAccessory = b'0x0b'
    cmdQueryPluginIdentifiers  = b'0x0c'
    cmdDetectPlugins = b'0x0d'
    cmdQueryStatus = b'0xfe'

    def __init__(self):
        self.device = usb.core.find(idVendor=USB2000.idVendor, idProduct=USB2000.idProduct)        

        if self.device is None:
            raise ValueError('Device not found')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(0,0)]

        self.ep1Out = self.interface[0]
        self.ep1In = self.interface[1]
        self.ep7In = self.interface[3]
        # self.ep1Out.write(b'0x01')
        # self.getSpectrumData()
        # self.ep1In.read(size_or_buffer=16, timeout=3000)
        #self.initializeDevice()

    def initializeDevice(self):
        self.ep1Out.write(b'0x01')
        # while True:
        #     self.ep1Out.write(b'0xfe')
        #     status = self.ep7In.read(size_or_buffer=16, timeout=3000)
        #     print(status)

    def setIntegrationTime(self, timeInMs):
        hi = timeInMs // 256
        lo = timeInMs % 256        
        self.ep1Out.write([USB2000.cmdSetIntegationTime[0], lo, hi])

    def requestSpectrum(self):
        self.ep1Out.write(b'0x09')
        # while not self.isSpectrumRequested():
        #     plt.pause(0.001)

    def isSpectrumRequested(self):
        self.ep1Out.write(b'0xfe')
        status = self.ep7In.read(size_or_buffer=16, timeout=1000)
        requested = status[6]
        return requested != 0

    def isSpectrumReady(self):
        self.ep1Out.write(b'0xfe')
        status = self.ep7In.read(size_or_buffer=16, timeout=1000)
        ready = status[8]
        return ready != 0

    def getStatus(self):
        self.ep1Out.write(b'0xfe')
        return self.ep7In.read(size_or_buffer=16, timeout=1000)

    def getSpectrumData(self):
        spectrum = []
        for packet in range(32):
            bytesReadLow = self.ep1In.read(size_or_buffer=64, timeout=1000)
            bytesReadHi = self.ep1In.read(size_or_buffer=64, timeout=1000)
            
            spectrum.extend(np.array(bytesReadLow)+256*np.array(bytesReadHi))

        confirmation = self.ep1In.read(size_or_buffer=1, timeout=2)
        assert(confirmation[0] == 0x69)
        return np.array(spectrum)

    def readEndpoints(self):
        try:
            while True:
                print(self.ep1In.read(size_or_buffer=1, timeout=1000))
        except:
            pass

        try:
            while True:
                print(self.ep7In.read(size_or_buffer=1, timeout=1000))
        except:
            pass

    def drawSpectrum(self):    
        while True:
            self.requestSpectrum()
            while not self.isSpectrumReady():
                plt.pause(0.001)
            spectrum = self.getSpectrumData()

            plt.clf()
            plt.plot(spectrum,'k.')
            plt.draw()
            plt.pause(0.001)

if __name__ == "__main__":
    spectrometer = USB2000()
    spectrometer.readEndpoints()
    # print(spectrometer.getStatus())
    # spectrometer.setIntegrationTime(5)
    #spectrometer.getSpectrumData()
    spectrometer.drawSpectrum()