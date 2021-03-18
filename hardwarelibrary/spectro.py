import tkinter

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
# Implement the default Matplotlib key bindings.
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure

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
        self.initializeDevice()
        self.getCalibration()
        self.fig = None

        if tkinter is not None:
            self.root = tkinter.Tk()
        else:
            self.root = None

    def initializeDevice(self):
        self.epCommandOut.write(b'0x01')

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
        parameters = self.epSecondaryIn.read(size_or_buffer=17, timeout=3000)
        return bytes(parameters[2:]).decode().rstrip('\x00')

    def requestSpectrum(self):
        self.epCommandOut.write(b'\x09')
        while not self.isSpectrumRequested():
            plt.pause(0.001)

    def isSpectrumRequested(self):
        status = self.getStatus()
        return status.isSpectrumRequested

    def isSpectrumReady(self):
        status = self.getStatus()
        return status.isSpectralDataReady

    def sendTextCommand(self, command):
        self.epCommandOut.write(command)
        try:
            while True:
                print(self.epMainIn.read(size_or_buffer=1, timeout=1000))
        except:
            print("Command failed")
            pass

    def getStatus(self):
        self.epCommandOut.write(b'\xfe')
        status = self.epSecondaryIn.read(size_or_buffer=16, timeout=3000)
        statusList = unpack('>hh?B???xxxxxxx',status)
        return Status(*statusList)

    def getSpectrumData(self):
        spectrum = []
        for packet in range(32):
            bytesReadLow = self.epMainIn.read(size_or_buffer=64, timeout=3000)
            bytesReadHi = self.epMainIn.read(size_or_buffer=64, timeout=3000)
            
            spectrum.extend(np.array(bytesReadLow)+256*np.array(bytesReadHi))

        confirmation = self.epMainIn.read(size_or_buffer=1, timeout=2)
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
        fig.set_size_inches(11, 8, forward=True)

        axes.set_xlabel("Wavelength [nm]")
        axes.set_ylabel("Intensity [arb.u]")
        return fig, axes

    def plotCurrentSpectrum(self, fig, axes):
        axes.cla()
        axes.set_xlabel("Wavelength [nm]")
        axes.set_ylabel("Intensity [arb.u]")
        spectrum = self.getSpectrum()
        axes.plot(self.wavelength, spectrum, 'k')
        plt.draw()

    def display(self):
        if self.root is not None:
            self.displayWithTkinter()
        else:
            self.displayWithMatplotlib()

    def displayWithMatplotlib(self, ax=None):
        fig, axes = self.createFigure()
        while True:
            self.plotCurrentSpectrum(fig, axes)
            plt.pause(0.001)

    def displayWithTkinter(self):
        fig, axes = self.createFigure()

        canvas = FigureCanvasTkAgg(fig, master=self.root)  # A tk.DrawingArea.
        self.plotCurrentSpectrum(fig, axes)
        canvas.draw()

        button = tkinter.Button(master=self.root, text="Quit", command=self.root.quit)

        # Packing order is important. Widgets are processed sequentially and if there
        # is no space left, because the window is too small, they are not displayed.
        # The canvas is rather flexible in its size, so we pack it last which makes
        # sure the UI controls are displayed as long as possible.
        button.pack(side=tkinter.BOTTOM)
        canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        self.refreshTkinterCanvas(fig, axes)
        tkinter.mainloop()

    def refreshTkinterCanvas(self, fig, axes):
        self.plotCurrentSpectrum(fig, axes)
        self.root.after(10, self.refreshTkinterCanvas, fig, axes)


if __name__ == "__main__":
    spectrometer = USB2000()
    spectrometer.setIntegrationTime(10)
    spectrometer.saveSpectrum('test.csv')
    spectrometer.display()

