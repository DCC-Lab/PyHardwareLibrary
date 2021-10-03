import os

import usb.core
import usb.util
import usb.backend.libusb1
import numpy as np

import matplotlib.backends as backends
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button, TextBox

class SpectraViewer:
    def __init__(self, spectrometer):
        """ A matplotlib-based window to display and manage a spectrometer
        to replace the insanely inept OceanView software from OceanInsight or 
        the dude-wtf?1 software from Stellarnet.
        If anybody reads this from Ocean Insight, you can direct people
        to this Python script.  It is simpler to call it directly from the
        spectrometer object with its own display function that will instantiate
        a SpectraViewer and call its display function with itself as a paramater.

        Parameters
        ----------

        spectrometer: Spectrometer
            A spectrometer from Ocean Insight or Stellarnet
        """

        self.spectrometer = spectrometer
        self.lastSpectrum = []
        self.whiteReference = None
        self.darkReference = None
        self.figure = None
        self.axes = None
        self.quitFlag = False
        self.saveBtn = None
        self.quitBtn = None
        self.lightBtn = None
        self.darkBtn = None
        self.integrationTimeBox = None
        self.animation = None

    def display(self):
        """ Display the spectrum in free-running mode, with simple
        autoscale, save and quit buttons as well as a text entry for
        the integration time. This is the only user-facing function that 
        is needed.
        """
        self.figure, self.axes = self.createFigure()

        self.setupLayout()
        self.quitFlag = False
        self.animation = animation.FuncAnimation(self.figure, self.animate, interval=100)
        plt.show()

    def createFigure(self):
        """ Create a matplotlib figure with decent properties. """

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
        fig.set_size_inches(10, 6, forward=True)
        serialNumber = self.spectrometer.getSerialNumber()
        model = self.spectrometer.model
        fig.canvas.manager.set_window_title('Spectrometer [serial # {0}, model {1}]'.format(serialNumber, model))
        axes.set_xlabel("Wavelength [nm]")
        axes.set_ylabel("Intensity [arb.u]")
        return fig, axes

    def setupLayout(self):
        axScale = plt.axes([0.125, 0.90, 0.13, 0.075])
        axLight = plt.axes([0.25, 0.90, 0.08, 0.075])
        axDark = plt.axes([0.30, 0.90, 0.08, 0.075])
        axTime = plt.axes([0.59, 0.90, 0.08, 0.075])
        axSave = plt.axes([0.73, 0.90, 0.08, 0.075])
        axQuit = plt.axes([0.82, 0.90, 0.08, 0.075])
        self.saveBtn = Button(axSave, 'Save')
        self.saveBtn.on_clicked(self.clickSave)
        self.quitBtn = Button(axQuit, 'Quit')
        self.quitBtn.on_clicked(self.clickQuit)
        self.autoscaleBtn = Button(axScale, 'Autoscale')
        self.autoscaleBtn.on_clicked(self.clickAutoscale)

        rootDir = os.path.dirname(os.path.abspath(__file__))

        try:
            axLight.imshow(plt.imread("{0}/lightbulb.png".format(rootDir)))
            axLight.set_xticks([])
            axLight.set_yticks([])
            self.lightBtn = Button(axLight,'')
        except:
            self.lightBtn = Button(axLight,'W')
        self.lightBtn.on_clicked(self.clickWhiteReference)

        try:
            axDark.imshow(plt.imread("{0}/darkbulb.png".format(rootDir)))
            axDark.set_xticks([])
            axDark.set_yticks([])
            self.darkBtn = Button(axDark,'') 
        except:
            self.darkBtn = Button(axDark,'D') 
        self.darkBtn.on_clicked(self.clickDarkReference)


        currentIntegrationTime = self.spectrometer.getIntegrationTime()
        self.integrationTimeBox = TextBox(axTime, 'Integration time [ms]',
                                          initial="{0}".format(currentIntegrationTime),
                                          label_pad=0.1)
        self.integrationTimeBox.on_submit(self.submitTime)
        self.figure.canvas.mpl_connect('key_press_event', self.keyPress)


    def plotSpectrum(self, spectrum=None):
        """ Plot a spectrum into the figure or request a new spectrum. This
        is called repeatedly when the display function is called."""
        if spectrum is None:
            spectrum = self.spectrometer.getSpectrum()

        if len(self.axes.lines) == 0:
            self.axes.plot(self.spectrometer.wavelength, spectrum, 'k')
            self.axes.set_xlabel("Wavelength [nm]")
            self.axes.set_ylabel("Intensity [arb.u]")
        else:
            self.axes.lines[0].set_data( self.spectrometer.wavelength, spectrum) # set plot data
            self.axes.relim()

    def animate(self, i):
        """ Internal function that is called repeatedly to manage the
        update  of the spectrum plot. It is better to use the `animation`
        strategy instead of a loop with  plt.pause() because plt.pause() will
        always bring the window to the  foreground. 

        This function is also responsible for determining if the user asked to quit. 
        """
        try:
            self.lastSpectrum = self.spectrometer.getSpectrum()
            if self.darkReference is not None:
                self.lastSpectrum -= self.darkReference
            if self.whiteReference is not None:
                np.seterr(divide='ignore',invalid='ignore')
                if self.darkReference is not None:
                    self.lastSpectrum = self.lastSpectrum / (self.whiteReference-self.darkReference)
                else:
                    self.lastSpectrum = self.lastSpectrum / self.whiteReference 

            self.plotSpectrum(spectrum=self.lastSpectrum)
        except usb.core.USBError as err:
            print("The spectrometer was disconnected. Quitting.")
            self.quitFlag = True

        if self.quitFlag:
            self.animation.event_source.stop()
            self.animation = None
            plt.close()

    def keyPress(self, event):
        """ Event-handling function for keypress: if the user clicks command-Q
        on macOS, it will nicely quit."""

        if event.key == 'cmd+q':
            self.clickQuit(event)
        if event.key == 'backspace':
            self.clickClearReferences(event)

    def submitTime(self, event):
        """ Event-handling function for when the user hits return/enter 
        in the integration time text field. The new integration time 
        is set in the spectrometer.

        We must autoscale the plot because the intensities could be very different.
        However, it takes a small amount of time for the spectrometer to react.
        We wait 0.3 seconds, which is small enough to not be annoying and seems to
        work fine.

        Anything incorrect will bring the integration time to 3 milliseconds.
        """
        try:
            time = float(self.integrationTimeBox.text)
            if time == 0:
                raise ValueError('Requested integration time is invalid: \
the text "{0}" converts to 0.')
            self.spectrometer.setIntegrationTime(time)
            plt.pause(0.3)
            self.axes.autoscale_view()
        except Exception as err:
            print("Error when setting integration time: ",err)
            self.integrationTimeBox.set_val("3")

    def clickAutoscale(self, event):
        """ Event-handling function to autoscale the plot """
        self.axes.autoscale_view()

    def clickClearReferences(self, event):
        """ Event-handling function to acquire a white reference """
        self.whiteReference = None
        self.lightBtn.color = '0.85'
        self.darkReference = None
        self.darkBtn.color = '0.85'
        plt.pause(0.3)
        self.axes.autoscale_view()

    def clickWhiteReference(self, event):
        """ Event-handling function to acquire a white reference """
        if self.whiteReference is None:
            self.whiteReference = self.spectrometer.getSpectrum()
            self.lightBtn.color = '0.99'
        else:
            self.whiteReference = None
            self.lightBtn.color = '0.85'
        plt.pause(0.3)
        self.axes.autoscale_view()

    def clickDarkReference(self, event):
        """ Event-handling function to acquire a dark reference """
        if self.darkReference is None:
            self.darkReference = self.spectrometer.getSpectrum()
            self.darkBtn.color = '0.99'
        else:
            self.darkReference = None
            self.darkBtn.color = '0.85'
        plt.pause(0.3)
        self.axes.autoscale_view()

    def clickSave(self, event):
        """ Event-handling function to save the file.  We stop the animation
        to avoid acquiring more spectra. The last spectrum acquired (i.e.
        the one displayed) after we have requested the filename. 
        The data is saved as a CSV file, and the animation is restarted.
        
        Technical note: To request the filename, we use different strategies on 
        different platforms.  On macOS, we can use a function from the backend.
        On Windows and others, we fall back on Tk, which is usually installed 
        with python.
        """

        self.animation.event_source.stop()
        filepath = "spectrum.csv"
        try:
            filepath = backends.backend_macosx._macosx.choose_save_file('Save the data',filepath)
        except:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            filepath = filedialog.asksaveasfilename()

        if filepath is not None:
            self.spectrometer.saveSpectrum(filepath, spectrum=self.lastSpectrum, 
                                           whiteReference=self.whiteReference,
                                           darkReference=self.darkReference)

        self.animation.event_source.start()

    def clickQuit(self, event):
        """ Event-handling function to quit nicely."""
        self.quitFlag = True