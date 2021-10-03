import time
import numpy as np
from struct import *
import csv
from typing import NamedTuple
import array
import re
import os
import sys
import platform
import inspect

import usb.core
import usb.util
import usb.backend.libusb1

from pathlib import *
from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.spectrometers.viewer import *

class NoSpectrometerConnected(RuntimeError):
    pass
class UnableToInitialize(RuntimeError):
    pass
class UnableToCommunicate(RuntimeError):
    pass
class SpectrumRequestTimeoutError(RuntimeError):
    pass

class Spectrometer(PhysicalDevice):
    idVendor = None
    idProduct = None
    def __init__(self, serialNumber=None, idProduct:int = None, idVendor:int = None):
        PhysicalDevice.__init__(self, serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.model = ""
        self.wavelength = np.linspace(400,1000,1024)
        self.integrationTime = 10

    def getSerialNumber(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def getSpectrum(self) -> np.array:
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def display(self):
        """ Display the spectrum with the SpectraViewer class."""
        viewer = SpectraViewer(spectrometer=self)
        viewer.display()

    def getIntegrationTime(self):
        return self.integrationTime

    def setIntegrationTime(self, value):
        self.integrationTime = value

    def saveSpectrum(self, filepath, spectrum=None, whiteReference=None, darkReference=None):
        """ Save a spectrum to disk as a comma-separated variable file.
        If no spectrum is provided, request one from the spectrometer withoout
        changing the integration time.

        Parameters
        ----------

        filepath: str
            The path and the filename where to save the data.  If no path
            is included, the file is saved in the current directory 
            with the python script was invoked.

        spectrum: array_like
            A spectrum previously acquired or None to request a new spectrum

        whiteReference: array_like
            A white reference to normalize the measurements

        darkReference: array_like
            A dark reference for baseline

        """

        try:
            if spectrum is None:
                spectrum = self.getSpectrum()
            if darkReference is None:
                darkReference = [0]*len(spectrum)
            if whiteReference is None:
                whiteReference = [1]*len(spectrum)

            with open(filepath, 'w', newline='\n') as csvfile:
                fileWrite = csv.writer(csvfile, delimiter=',')
                fileWrite.writerow(['Wavelength [nm]','Intensity [arb.u]','White reference','Dark reference'])
                for x,y,w,d in list(zip(self.wavelength, spectrum, whiteReference, darkReference)):
                    fileWrite.writerow(["{0:.2f}".format(x),y,w,d])
        except Exception as err:
            print("Unable to save data: {0}".format(err))

    @classmethod
    def supportedClasses(cls):
        supportedClasses = []
        for c in getAllSubclasses(Spectrometer):
            classSearch = re.search(r'\.(USB.*?)\W', "{0}".format(c), re.IGNORECASE)
            if classSearch:
                supportedClasses.append(c)
        return supportedClasses

    @classmethod
    def supportedClassNames(cls):
        supportedClasses = []
        for c in getAllSubclasses(Spectrometer):
            classSearch = re.search(r'\.(USB.*?)\W', "{0}".format(c), re.IGNORECASE)
            if classSearch:
                supportedClasses.append(classSearch.group(1))
        return supportedClasses

    @classmethod
    def showHelp(cls, err=None):
        print("""
    There may be missing modules, missing spectrometer or anything else.
    To use this `{0}` python script, you *must* have:

    1. PyUSB module installed. 
       This can be done with `pip install pyusb`.  On some platforms, you
       also need to install libusb, a free package to access USB devices.  
       On Windows, you can leave the libusb.dll file directly in the same
       directory as this script.  If no spectrometers are detected, it is
       possible the problem is due to libusb.dll not being in the directory
       where `{0}` was called.
    2. A backend for PyUSB.
       PyUSB does not communicate by itself with the USB ports of your
       computer. A 'backend' (or library) is needed.  Typically, libusb is
       used. You must  install libusb (or another compatible library). On
       macOS: type `brew install libusb` (if you have brew). If not,  get
       `brew`. On Windows/Linux, go read the PyUSB tutorial:
       https://github.com/pyusb/pyusb/blob/master/docs/tutorial.rst
       If you have libusb.dll on Windows, keep it in the same 
       directory as {0} and it should work.
    3. matplotlib module installed
       If you want to use the display function, you need matplotlib.
       This can be installed with `pip install matplotlib`
    4. Tkinter module installed.
       If you click "Save" in the window, you may need the Tkinter module.
       This comes standard with most python distributions.
    5. Obviously, a connected Ocean Insight or StellarNet spectrometer. It really needs to be 
       a supported spectrometer ({1}).  The details of all 
       the spectrometers are different (number of pixels, bits, wavelengths,
       speed, etc...). More spectrometers will be supported in the future.
       Look at the class USB2000 to see what you have to provide to support
       a new spectrometer (it is not that much work, but you need one to test).
""".format(__file__, ', '.join(Spectrometer.supportedClassNames)))

        # Well, how about that? This does not work in Windows
        # https://stackoverflow.com/questions/2330245/python-change-text-color-in-shell
        # if sys.stdout.isatty:
        #     err = '\x1b[{0}m{1}\x1b[0m'.format(';'.join(['33','1']), err)

        print("""    There was an error when starting: '{0}'.
    See above for help.""".format(err))

    @classmethod
    def displayAny(cls):
        spectrometer = cls.any()
        if spectrometer is not None:
            SpectraViewer(spectrometer).display()

    @classmethod
    def any(cls) -> 'Spectrometer':
        """ Return the first supported spectrometer found as a Python object
        that can be used immediately.

        Returns
        -------
        device: subclass of Spectrometer
            An instance of a supported spectrometer that can be used immediately.
        """

        devices = cls.connectedUSBDevices()
        for device in devices:
            for aClass in cls.supportedClasses():
                if device.idProduct == aClass.classIdProduct:
                    return aClass(serialNumber="*", idProduct=device.idProduct, idVendor=device.idVendor)

        if len(devices) == 0:
            raise NoSpectrometerConnected('No spectrometer connected.')
        else:
            raise NoSpectrometerConnected('No supported spectrometer connected. The devices {0} are not supported.'.format(devices))

    @classmethod
    def connectedUSBDevices(cls, idProduct=None, serialNumber=None):
        """ 
        Return a list of supported USB devices that are currently connected.
        If idProduct is provided, match only these products. If a serial
        number is provided, return the matching device otherwise return an
        empty list. If no serial number is provided, return all devices.

        Parameters
        ----------
        idProduct: int Default: None
            The USB idProduct to match
        serialNumber: str Default: None
            The serial number to match, when there are still more than one device after
            filtering out the idProduct.  If there is a single match, the serial number
            is disregarded.

        Returns
        -------

        devices: list of Device
            A list of connected devices matching the criteria provided
        """
        idVendors = set()
        for aClass in cls.supportedClasses():
            if aClass is not None:
                idVendors.add(aClass.classIdVendor)

        devices = []
        if idProduct is None:
            for idVendor in idVendors:
                devices.extend(list(usb.core.find(find_all=True, idVendor=idVendor)))
        else:
            for idVendor in idVendors:
                devices.extend(list(usb.core.find(find_all=True, idVendor=idVendor, idProduct=idProduct)))

        if serialNumber is not None: # A serial number was provided, try to match
            for device in devices:
                deviceSerialNumber = usb.util.get_string(device, device.iSerialNumber ) 
                if deviceSerialNumber == serialNumber:
                    return [device]

            return [] # Nothing matched

        return devices

    @classmethod
    def matchUniqueUSBDevice(cls, idProduct=None, serialNumber=None):
        """ A class method to find a unique device that matches the criteria provided. If there
        is a single device connected, then the default parameters will make it return
        that single device. The idProduct is used to filter out unwanted products. If
        there are still more than one of the same product type, then the serial number
        is used to separate them. If we can't find a unique device, we raise an
        exception to suggest what to do. 

        Parameters
        ----------
        idProduct: int Default: None
            The USB idProduct to match
        serialNumber: str Default: None
            The serial number to match, when there are still more than one after
            filtering out the idProduct.  if there is a single match, the serial number
            is disregarded.

        Returns
        -------

        device: Device
            A single device matching the criteria

        Raises
        ------
            RuntimeError if a single device cannot be found.
        """

        devices = cls.connectedUSBDevices(idProduct=idProduct, 
                                          serialNumber=serialNumber)

        device = None
        if len(devices) == 1:
            device = devices[0]
        elif len(devices) > 1:
            if serialNumber is not None:
                raise NoSpectrometerConnected('Device with the appropriate serial number ({0}) was not found in the list of devices {1}'.format(serialNumber, devices))
            else:
                # No serial number provided, just take the first one
                device = devices[0]
        else:
            # No devices with criteria provided
            anySpectroDevice = Spectrometer.connectedUSBDevices()
            if len(anySpectroDevice) == 0:
                raise NoSpectrometerConnected('Device not found because there are no spectrometer devices connected.')
            else:
                raise NoSpectrometerConnected('Device not found. There are spectrometer devices connected {0}, but they do not match either the model or the serial number requested.'.format(anySpectroDevice))

        return device

def getAllSubclasses(aClass):
    allSubclasses = []
    for subclass in aClass.__subclasses__():
        if len(subclass.__subclasses__()) == 0:
            allSubclasses.append(subclass)
        else:
            allSubclasses.extend(getAllSubclasses(subclass))

    return allSubclasses


if __name__ == "__main__":
    print(Spectrometer)
    print(getAllSubclasses(Spectrometer))
