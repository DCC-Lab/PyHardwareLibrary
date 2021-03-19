import matplotlib
import matplotlib.animation as animation
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.widgets import Button

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

class GraphicsData(NamedTuple):
    figure:Figure = None
    axes:Axes = None

class USB2000:
    idVendor = 0x2457
    idProduct = 0x1002
    def __init__(self):
        self.device = usb.core.find(idVendor=self.idVendor, 
                                    idProduct=self.idProduct)        

        if self.device is None:
            raise ValueError('Device not found')

        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(0,0)]

        self.epCommandOut = self.interface[0]
        self.epMainIn = self.interface[1]
        self.epSecondaryIn = self.interface[3]
        self.lastSpectrum = []

        self.initializeDevice()

        self.graphics = GraphicsData()
        self.quitFlag = False
        self.saveBtn = None
        self.animation = None

    def initializeDevice(self):
        self.epCommandOut.write(b'0x01')
        self.getCalibration()

    def shutdownDevice(self):
        return

    def setIntegrationTime(self, timeInMs):
        hi = timeInMs // 256
        lo = timeInMs % 256        
        self.epCommandOut.write([0x02, lo, hi])

    def getCalibration(self):
        status = self.getStatus()
        self.a0 = float(self.getParameter(index=1))
        self.a1 = float(self.getParameter(index=2))
        self.a2 = float(self.getParameter(index=3))
        self.a3 = float(self.getParameter(index=4))
        self.wavelength = [ self.a0 + self.a1*x + self.a2*x*x + self.a3*x*x*x 
                            for x in range(status.pixels)]

    def getParameter(self, index):
        self.epCommandOut.write([0x05, index])        
        parameters = self.epSecondaryIn.read(size_or_buffer=17, timeout=5000)
        return bytes(parameters[2:]).decode().rstrip('\x00')

    def requestSpectrum(self):
        self.epCommandOut.write(b'\x09')
        timeOut = time.time() + 1
        while not self.isSpectrumRequested():
            time.sleep(0.001)
            if time.time() > timeOut:
                raise TimeoutError()

    def isSpectrumRequested(self):
        status = self.getStatus()
        return status.isSpectrumRequested

    def isSpectrumReady(self):
        status = self.getStatus()
        return status.isSpectralDataReady

    def getStatus(self):
        self.epCommandOut.write(b'\xfe')
        status = self.epSecondaryIn.read(size_or_buffer=16, timeout=5000)
        statusList = unpack('>hh?B???xxxxxxx',status)
        return Status(*statusList)

    def getSpectrumData(self):
        spectrum = []
        for packet in range(32):
            bytesReadLow = self.epMainIn.read(size_or_buffer=64, timeout=5000)
            bytesReadHi = self.epMainIn.read(size_or_buffer=64, timeout=5000)
            
            spectrum.extend(np.array(bytesReadLow)+256*np.array(bytesReadHi))

        confirmation = self.epMainIn.read(size_or_buffer=1, timeout=5000)
        spectrum[0] = spectrum[1]

        assert(confirmation[0] == 0x69)
        return np.array(spectrum)

    def getSpectrum(self, integrationTime=None):
        if integrationTime is not None:
            self.setIntegrationTime(integrationTime)

        self.requestSpectrum()
        timeOut = time.time() + 1
        while not self.isSpectrumReady():
            time.sleep(0.001)
            if time.time() > timeOut:
                raise TimeoutError("Data never ready")

        return self.getSpectrumData()

    def saveSpectrum(self, filepath, spectrum=None):
        try:
            if spectrum is None:
                spectrum = self.getSpectrum()

            with open(filepath, 'w', newline='\n') as csvfile:
                fileWrite = csv.writer(csvfile, delimiter=',')
                fileWrite.writerow(['Wavelength [nm]','Intensity [arb.u]'])
                for x,y in list(zip(self.wavelength, spectrum)):
                    fileWrite.writerow(["{0:.2f}".format(x),y])
        except:
            print("Unable to save data.")

    def display(self, ax=None):
        fig, axes = self.createFigure()
        self.graphics = GraphicsData( fig, axes)

        axQuit = plt.axes([0.7, 0.90, 0.1, 0.075])
        axSave = plt.axes([0.81, 0.90, 0.1, 0.075])
        self.saveBtn = Button(axSave, 'Save')
        self.saveBtn.on_clicked(self.clickSave)
        quitBtn = Button(axQuit, 'Quit')
        quitBtn.on_clicked(self.clickQuit)
        fig.canvas.mpl_connect('key_press_event', self.keyPress)

        self.quitFlag = False
        self.animation = animation.FuncAnimation(fig, self.animate, interval=25)
        plt.show()

    def createFigure(self):
        SMALL_SIZE = 14
        MEDIUM_SIZE = 18
        BIGGER_SIZE = 36

        plt.rc('font', size=SMALL_SIZE)  # controls default text sizes
        plt.rc('axes', titlesize=SMALL_SIZE)  # fontsize of the axes title
        plt.rc('axes', labelsize=MEDIUM_SIZE)  # fontsize of the x and y labels
        plt.rc('xtick', labelsize=MEDIUM_SIZE)  # fontsize of the tick labels
        plt.rc('ytick', labelsize=MEDIUM_SIZE)  # fontsize of the tick labels
        plt.rc('legend', fontsize=SMALL_SIZE)  # legend fontsize
        plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title

        fig, axes = plt.subplots()
        fig.set_size_inches(9, 6, forward=True)

        axes.set_xlabel("Wavelength [nm]")
        axes.set_ylabel("Intensity [arb.u]")
        return fig, axes

    def plotCurrentSpectrum(self, fig, axes, spectrum=None):
        try:
            if spectrum is None:
                spectrum = self.getSpectrum()

            if len(axes.lines) == 0:
                axes.plot(self.wavelength, spectrum, 'k')
                axes.set_xlabel("Wavelength [nm]")
                axes.set_ylabel("Intensity [arb.u]")
            else: 
                axes.lines[0].set_data( self.wavelength, spectrum) # set plot data
        except:
            pass

    def animate(self, i):
        if self.quitFlag:
            self.animation.event_source.stop()
            self.animation = None
            plt.close()

        self.lastSpectrum = self.getSpectrum()
        self.plotCurrentSpectrum(self.graphics.figure, self.graphics.axes, spectrum=self.lastSpectrum)

    def keyPress(self, event):
        if event.key == 'cmd+q':
            self.quitFlag = True

    def clickSave(self, event):
        self.animation.event_source.stop()
        filepath = "spectrum.csv"
        try:
            filepath = matplotlib.backends.backend_macosx._macosx.choose_save_file('Save the data',filepath)
        except:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            filepath = filedialog.asksaveasfilename()

        if filepath is not None: 
            self.saveBtn.label.set_text("••••")
            self.saveSpectrum(filepath, spectrum=self.lastSpectrum)
            #plt.savefig("{0}.pdf".format(filepath),dpi=600)
            self.saveBtn.label.set_text("Save")

        self.animation.event_source.start()

    def clickQuit(self, event):
        self.quitFlag = True


if __name__ == "__main__":
    spectrometer = USB2000()
    spectrometer.setIntegrationTime(10)
    spectrometer.saveSpectrum('test.csv')
    spectrometer.display()

