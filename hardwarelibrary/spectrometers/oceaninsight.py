try:
    import time
    import numpy as np
    from struct import *
    import csv
    from typing import NamedTuple
    import array

    import usb.core
    import usb.util

    import matplotlib.backends as backends
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib.widgets import Button, TextBox

except Exception as err:
    print('** Error importing modules. {0}'.format(err))
    print('We will attempt to continue and hope for the best.')
    
"""
This is a simple script to use an Ocean Insight USB2000 spectrometer. You can
use a simple interface or just use the USB2000 class and integrate it in your
own project.

If you simply run `python oceaninsight.py`, you wil get a spectrum in
real-time that you can view and save.

The USB2000 class encapsulates all the functions to access the device:  it
instantiates a communication channel with the device with PyUSB, which needs
to be installed and operational. All functions that access the USB
communication to the spectrometer start with: 'get' and 'set'. A convenience
display() function will create a SpectraViewer and call it with itself as a
parameter.  The USB2000 class can easily be used in your own program and does not
depend on GUI modules.

The SpectraViewer class includes all functions to display the spectra and manage 
user interactions. If you don't use SpectraViewer, you don't need matplotlib
or Tkinter.

Note
----

This project aims to replace the ill-conceived, shame-inducing, mind-boggingly
sucky OceanView "software"-ish that Ocean Insight appears to think is a decent option
for reasonable human beings to do science. It is not. Shame on you. On the bright
side, the OEM documentation for their spectrometers is excellent, so this 
implementation was not difficult to code.

It is in a single python file to simplify usage by others.

"""

class Status(NamedTuple):
    """
    Status of the Ocean Insight spectrometer. NamedTuple are compatible
    with regular tuples but allow access with names instead of indexes,
    simplifying usage.
    
    Attributes
    ----------
    pixels : int
        number of pixels on the sensors
    integrationTime: int
        integration time in milliseconds
    isLampEnabled : bool
        lamp strobe (connected on specific pin) is enabled
    triggerMode : int
        trigger mode: normal (freerunning, software or external)
    isSpectrumRequested: bool
        A spectrum is currently being acquired and prepared for transfer.
    timerSwap: bool
        Use an 8-bit timer or 16-bit timer for integration. Default 16-bit
    isSpectralDataReady : bool
        The spectrum requested is ready to be transferred.
    """
    pixels : int = None
    integrationTime: int = None
    isLampEnabled : bool = None
    triggerMode : int = None    
    isSpectrumRequested: bool = None
    timerSwap: bool = None
    isSpectralDataReady : bool = None

class StatusUSB4000(NamedTuple):
    """
    Status of the USB4000 Ocean Insight spectrometer. NamedTuple are compatible
    with regular tuples but allow access with names instead of indexes,
    simplifying usage.
    
    Attributes
    ----------
    pixels : int
        number of pixels on the sensors
    integrationTime: long
        integration time in milliseconds
    isLampEnabled : bool
        lamp strobe (connected on specific pin) is enabled
    triggerMode : int
        trigger mode: normal (freerunning, software or external)
    isSpectrumRequested: bool
        A spectrum is currently being acquired and prepared for transfer.
    nPackets: int
        Number of packets per spectra
    powerDown: bool
        Circuit is powered down
    usbSpeed : int
        Speed of USB communication: 0 : full 0x80 : high
    """
    pixels : int = None
    integrationTime: int = None
    isLampEnabled : bool = None
    triggerMode : int = None    
    acquisitionStatus: int = None
    packetCount: int = None
    powerDown : bool = None
    packetsTransferred: int = None
    isHighSpeed : bool = None

class OISpectrometer:
    """
    An Ocean insight (Ocean Optics) spectrometer.  This allows complete access
    to the hardware with simple functions to get the spectrum, or modify the
    integration time.
    
    Access to the device is done with pyusb and does not require any
    additional information. The USB-specific attributes of the spectrometers are
    available,  but are not needed for standard usage.  If you need to
    implement additional functions and communicate with the device (not all
    capabilities are currently coded), then you could implement them in a
    separate function.

    Methods starting with "get" and "set" will actually communication with the
    spectrometer and correspond to a command as defined in the OEM manual
    "USB2000 Data Sheet". The manuals can be found here:
    https://github.com/DCC-Lab/PyHardwareLibrary/tree/master/hardwarelibrary/manuals

    Attributes
    ----------
    idVendor: int
        USB idVendor for OceanInsight (0x2457)

    idProduct: int
        USB idProduct for spetrometer (e.g., USB2000 is 0x1002)

    wavelength: np.array(float)
        The wavelength corresponding to each pixel, as obtained from 
        factory calibration

    device : Device
        The USB device as obtained from pyusb core.find()

    configuration: Configuration
        The active USB configuration

    interface: Interface
        The active USB interface from the configuration

    serialNumber: str
        The serial number from the USB configuration descriptor

    epCommandOut: EndPoint
        The USB endpoint (i.e. the USB communication channel) to send commands

    epMainIn: EndPoint
        The USB endpoint (i.e. the USB communication channel) to receive replies
        for most commands

    epSecondaryIn: EndPoint
        The USB endpoint (i.e. the USB communication channel) to receive replies
        for spectral data and other commands

    """
    idVendor = 0x2457 # Ocean Insight USB idVendor

    def __init__(self, idProduct, model, serialNumber=None):
        """
        Finds and initialize the communication with the Ocean Insight spectrometer
        if there is one connected. All subclasses must provide the USB product id
        that corresponds to this model (0x1002 for USB2000 for instance) and 
        a string that describes the model, for the user.

        If two spectrometers of the same model are connected, it will match the serial
        number. If a serial number is not provided, it will take the first one. 
        This may not always be the one you expect or the same every day: it depends
        on many things that you don't control.  Just find out the serial number
        and use it.

        USB Details
        -----------

        The USB protocol is daunting for beginners and even for advanced
        programmers. It is not the place here to explain all the details,  but
        if you need to understand, here is the minimum info. The USB  protocol
        helps define the details for any device (it is *extremely* general). A device,
        when connected, needs to be configured for our purpose.

        1. A device has a "USB Configuration" that we can retrieve. 
        2. That configuration has a "USB Interface" that we pick to determine
        what we want to do with the device.
        3. That device defines communication channels (EndPoints) that are
        either input or output. Contrary to a simple serial port that has a
        single output channel and a single input channel, the USB port can
        have many  of those channels (i.e. endpoints) that can be used for
        different purpose.  For instance,  the OI Spectrometers have a channel
        for commands Input/Output and an input channel to send the data. All
        of those USB details are highly device-sepcific.  

        Ocean Insight spectrometers have 1 USB configuration descriptor only,
        we can use the default when configuring. Also, they appear to have a
        single USB interface without alternate settings, se we can use (0,0)
        to retrieve the appropriate one. Finally, reading the documentation 
        for several OI spectrometers seems to indicate that the first input
        and output channels are the main channels, and the second input
        channel is for data.

        Parameters
        ----------

        idProduct: int
            The USB product id for the spectrometer, found in the documentation
            or by connecting it.
        model: str
            A model name to be displayed to the user
        serialNumber: str Default None
            A serial number that can be used to specify which spectrometer
            we want to use when there are more than one connected. Most of the
            time, this is not needed, we simply pick the first one if no
            serial number is provided.
        """

        self.idProduct = idProduct
        self.model = model
        self.device = OISpectrometer.matchUniqueUSBDevice( idProduct=idProduct, 
                                       serialNumber=serialNumber)

        """ Below are all the USB protocol details.  This requires reading
        the USB documentation, the Spectrometer documentation and many other 
        details. What follows may sound like gibberish.

        There is a single USB Configuration (default) with a single USB Interface 
        without alternate settings, so we can use (0,0).
        """
        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(0,0)]

        """
        We are working on the reasonable assumption from the documentation
        that the first input and output endpoints are the main endpoints and the
        second input is the data endpoint. If that is not the case, the subclass can
        simply reassign the endpoints properly in its __init__ function. 
        """
        self.inputEndpoints = []
        self.outputEndpoints = []
        for endpoint in self.interface:
            """ The endpoint address has the 8th bit set to 1 when it is an input.
            We can check with the bitwise operator & (and) 0x80. It will be zero
            if an output and non-zero if an input. """
            if endpoint.bEndpointAddress & 0x80 != 0:
                self.inputEndpoints.append(endpoint)
            else:
                self.outputEndpoints.append(endpoint)

        self.epCommandOut = None
        self.epMainIn = None
        self.epSecondaryIn = None
        if len(self.inputEndpoints) >= 2 or len(self.outputEndpoints) > 0:
            """ We have at least 2 input endpoints and 1 output. We assign the
            endpoints according to the documentation, otherwise
            the subclass will need to assign them."""
            self.epCommandOut = self.outputEndpoints[0]
            self.epMainIn = self.inputEndpoints[0]
            self.epSecondaryIn = self.inputEndpoints[1]

        self.wavelength = None
        self.discardLeadingSamples = 0 # In some models, the leading data is meaningless
        self.discardTrailingSamples = 0 # In some models, the trailing data is meaningless
        self.lastStatus = None

    def initializeDevice(self):
        """
        Initialize the Spectrometer and obtain calibration information.
        This commands needs to be sent only once per session as soon as 
        the communication is started.
        """
        try:
            self.flushEndpoints()
            self.epCommandOut.write(b'0x01')
            time.sleep(0.1)
            self.getCalibration()
        except Exception as err:
            raise RuntimeError("Error when initializing device: {0}".format(err))

    def shutdownDevice(self):
        """
        Shutdown the Spectrometer. Currently does not perform anything.
        """
        return

    def flushEndpoints(self):
        for endpoint in self.inputEndpoints:
            try:
                while True:
                    buffer = array.array('B',[0]*endpoint.wMaxPacketSize)
                    endpoint.read(size_or_buffer=buffer, timeout=100)
            except usb.core.USBTimeoutError as err:
                pass # This is an expected error if the buffers are empty.
            except Exception as err:
                print("Unable to flush buffers: {0}".format(err))

    def setIntegrationTime(self, timeInMs):
        """ Set the integration time in an integer value of milliseconds 
        for a spectrum. If the value is smaller than 3 ms, it will be unchanged.
        """
        timeInMs = int(timeInMs)
        hi = timeInMs // 256
        lo = timeInMs % 256        
        self.epCommandOut.write([0x02, lo, hi])

    def getIntegrationTime(self):
        """ Get the integration time in as an integer value in milliseconds
        """
        status = self.getStatus()
        return status.integrationTime

    def getSerialNumber(self):
        """ Get the serial nunmber of the spectrometer.  This can be used to
        differentiate two connected spectrometers.
        """
        return self.getParameter(index=0)

    def getCalibration(self):
        """ Get the hardcoded calibration from the spectrometer.  It is a
        3rd-order polynomial. Currently, no nonlinearities are considered.
        """
        self.a0 = float(self.getParameter(index=1))
        self.a1 = float(self.getParameter(index=2))
        self.a2 = float(self.getParameter(index=3))
        self.a3 = float(self.getParameter(index=4))
        status = self.getStatus()
        self.wavelength = [ self.a0 + self.a1*x + self.a2*x*x + self.a3*x*x*x 
                            for x in range(status.pixels)]
        if self.discardTrailingSamples > 0:
            self.wavelength = self.wavelength[:-self.discardTrailingSamples]
        if self.discardLeadingSamples > 0:
            self.wavelength = self.wavelength[self.discardLeadingSamples:]

    def getParameter(self, index):
        """ Get any of the 20 parameters hardcoded into the spectrometer.

        Parameters
        ----------

        index: int
            0 – Serial Number
            1 – 0th order Wavelength Calibration Coefficient 
            2 – 1st order Wavelength Calibration Coefficient
            3 – 2nd order Wavelength Calibration Coefficient 
            4 – 3rd order Wavelength Calibration Coefficient 
            5 – Stray light constant
            6 – 0th order non-linearity correction coefficient
            7 – 1st order non-linearity correction coefficient
            8 – 2nd order non-linearity correction coefficient
            9 – 3rd order non-linearity correction coefficient
            10 – 4th order non-linearity correction coefficient
            11 – 5th order non-linearity correction coefficient
            12 – 6th order non-linearity correction coefficient
            13 – 7th order non-linearity correction coefficient
            14 – Polynomial order of non-linearity calibration
            15 – Optical bench configuration: gg fff sss gg – Grating #, fff – filter wavelength, sss – slit size 
            16 - Spectrometer configuration: AWL V
                A – Array coating Mfg, 
                W – Array wavelength (VIS, UV, OFLV), 
                L – L2 lens installed, 
                V – CPLD Version
            17 – Reserved
            18 – Reserved
            19 – Reserved

        Returns
        -------
        parameter : str 
            The value of the parameter as an ASCII string
        """
        self.epCommandOut.write([0x05, index])
        parameters = array.array('B',[0]*self.epSecondaryIn.wMaxPacketSize)
        self.epSecondaryIn.read(size_or_buffer=parameters, timeout=5000)
        return bytes(parameters[2:]).decode().rstrip('\x00')

    def requestSpectrum(self):
        """ Requests a spectrum.  The command will not return until the 
        spectrometer acknowledges that it did receive the request and flags
        it properly in its operating status. If after 1 second the request 
        has not been processed, it will raise a TimeoutError exception. """

        self.epCommandOut.write(b'\x09')
        timeOut = time.time() + 1
        while not self.isSpectrumRequested():
            time.sleep(0.001)
            if time.time() > timeOut:
                raise TimeoutError('The spectrometer never acknowledged the reception of the spectrum request')

    def isSpectrumRequested(self) -> bool:
        """ The spectrometer is currently waiting for an acquisition to 
        complete and will raise the ready flag when the spectrum is ready
        to be retrieved.

        Returns
        -------
        isSpectrumRequested : bool 
            Whether or not the spectrometer is waiting for an acquisition 
        """
        status = self.getStatus()
        return status.isSpectrumRequested

    def isSpectrumReady(self):
        """ The requested spectrum is ready to be retrieved with getSpectrumData.

        Returns
        -------
        isSpectrumReady : bool 
            Whether or not the spectrum ready to be retrieved
        """
        status = self.getStatus()
        return status.isSpectralDataReady

    def getStatus(self):
        """ The status of the spectrometer returned as a Status named tuple.

        Returns
        -------
        status : Status 
            You can access the fields of the status by index (i.e. status[0]) or
            via their names. See the `Status` class.

            pixels : int = None
            integrationTime: int = None
            isLampEnabled : bool = None
            triggerMode : int = None    
            isSpectrumRequested: bool = None
            timerSwap: bool = None
            isSpectralDataReady : bool = None
       
        """
        self.epCommandOut.write(b'\xfe')
        status = self.epSecondaryIn.read(size_or_buffer=16, timeout=1000)
        statusList = unpack('>hh?B???xxxxxxx',status)
        status = Status(*statusList)
        self.lastStatus = status
        return status

    def getSpectrumData(self):
        """ Retrieve the spectral data.  You must call requestSpectrum first.
        If the spectrum is not ready yet, it will simply wait. The timeout 
        is set short so it may timeout.  You would normally check with
        isSpectrumReady before calling this function.
        This is highly device specific and must be implemented by the subclass.

        Returns
        -------
        spectrum : np.array(float)
            The spectrum, in integers corresponding to each wavelength
            available in self.wavelength.
        """
        raise NotImplementedError('You must implemented getSpectrumData for your subclass.')

    def getSpectrum(self, integrationTime=None):
        """ Obtain a spectrum from the spectrometer. This implies:
        1- changing the integration time if needed.
        2- requesting a spectrum,
        3- waiting until ready, then 
        4- actually retrieving and returning the data.
        
        Parameters
        ----------
        integrationTime: int, default None 
            integration time in milliseconds if not the currently configured
            time.

        Returns
        -------

        spectrum : np.array(float)
            The spectrum, in 16-bit integers corresponding to each wavelength
            available in self.wavelength.
        """
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

        """

        try:
            if spectrum is None:
                spectrum = self.getSpectrum()

            with open(filepath, 'w', newline='\n') as csvfile:
                fileWrite = csv.writer(csvfile, delimiter=',')
                fileWrite.writerow(['Wavelength [nm]','Intensity [arb.u]'])
                for x,y in list(zip(self.wavelength, spectrum)):
                    fileWrite.writerow(["{0:.2f}".format(x),y])
        except Exception as err:
            print("Unable to save data: {0}".format(err))

    def display(self):
        """ Display the spectrum with the SpectraViewer class."""
        viewer = SpectraViewer(spectrometer=self)
        viewer.display()

    @classmethod
    def showHelp(cls, err=None):
        if err is not None:
            print("There was an error when starting: '{0}'".format(err))

        print("""
    There may be missing modules, missing spectrometer or anything else.
    To use this `{0}` python script, you *must* have:

    1. PyUSB module installed. 
        This can be done with `pip install pyusb`.  On some platforms, you
        also need to install libusb, a free package to access USB devices.  
        On Windows, you can leave the libusb.dll file directly in the same
        directory as this script.
    2. matplotlib module installed
        If you want to use the display function, you need matplotlib.
        This can be installed with `pip install matplotlib`
    3. Tkinter module installed.
        If you click "Save" in the window, you may need the Tkinter module.
        This comes standard with most python distributions.
    4. Obviously, a connected Ocean Insight spectrometer. It really needs to be 
        a supported spectrometer (only USB2000 for now).  The details of all 
        the spectrometers are different (number of pixels, bits, wavelengths,
        speed, etc...). More spectrometers will be supported in the future.
        Look at the class USB2000 to see what you have to provide to support
        a new spectrometer (it is not that much work, but you need one to test).
                """.format(__file__)
                )

    @classmethod
    def any(cls) -> 'OISpectrometer':
        """ Return the first supported spectrometer found as a Python object
        that can be used immediately.

        Returns
        -------
        device: subclass of OISpectrometer
            An instance of a supported spectrometer that can be used immediately.
        """

        supportedClasses = cls.__subclasses__()

        devices = cls.connectedUSBDevices()
        for device in devices:
            for aClass in supportedClasses:
                if device.idProduct == aClass.idProduct:
                    return aClass()

        if len(devices) == 0:
            raise RuntimeError('No Ocean Optics spectrometer connected.')
        else:
            raise RuntimeError('No supported Ocean Optics spectrometer connected. The devices {0} are not supported.'.format(devices))

    @classmethod
    def connectedUSBDevices(cls, idProduct=None, serialNumber=None):
        """ Return a list of USB devices from Ocean Insight that are currently
        connected. If idProduct is provided, match only these products.
        If a serial number is provided, return the matching device otherwise return 
        an empty list.
        If no serial number is provided, return all devices.

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

        devices: list of Device
            A list of connected devices matching the criteria provided
        """
        if idProduct is None:
            devices = list(usb.core.find(find_all=True, idVendor=cls.idVendor))
        else:
            devices = list(usb.core.find(find_all=True, 
                                    idVendor=cls.idVendor, 
                                    idProduct=idProduct))

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

        devices = OISpectrometer.connectedUSBDevices(idProduct=idProduct, 
                                                  serialNumber=serialNumber)

        device = None
        if len(devices) == 1:
            device = devices[0]
        elif len(devices) > 1:
            if serialNumber is not None:
                raise RuntimeError('Ocean Insight device with the appropriate serial number ({0}) was not found in the list of devices {1}'.format(serialNumber, devices))
            else:
                # No serial number provided, just take the first one
                device = devices[0]
        else:
            # No devices with criteria provided
            anyOIDevices = OISpectrometer.connectedUSBDevices()
            if len(anyOIDevices) == 0:
                raise RuntimeError('Ocean Insight device not found because there are no Ocean Insight devices connected.'.format())
            else:
                raise RuntimeError('Ocean Insight device not found. There are Ocean Insight devices connected {1}, but they do not match either the model or the serial number requested.'.format(anyOIDevices))

        return device


class USB2000(OISpectrometer):
    """
    A USB2000 spectrometer.  The main differences:
    1. The idProduct is 0x1002
    2. The integration time is 16-bit
    3. The format of the retrieved data is different for each spectrometer.

    """
    idProduct = 0x1002
    def __init__(self):
        OISpectrometer.__init__(self, idProduct=USB2000.idProduct, model="USB2000")
        self.initializeDevice()

    def getSpectrumData(self):
        """ Retrieve the spectral data.  You must call requestSpectrum first.
        If the spectrum is not ready yet, it will simply wait. The timeout 
        is set short so it may timeout.  You would normally check with
        isSpectrumReady before calling this function.

        The format for the USB2000 is all the least significant bytes in a packet
        then the most significant bytes. We combine them to get the values.

        Returns
        -------
        spectrum : np.array(float)
            The spectrum, in 16-bit integers corresponding to each wavelength
            available in self.wavelength.
        """
        spectrum = []
        for packet in range(32):
            bytesReadLow = self.epMainIn.read(size_or_buffer=64, timeout=200)
            bytesReadHi = self.epMainIn.read(size_or_buffer=64, timeout=200)
            
            spectrum.extend(np.array(bytesReadLow)+256*np.array(bytesReadHi))

        confirmation = self.epMainIn.read(size_or_buffer=1, timeout=200)
        spectrum[0] = spectrum[1]

        assert(confirmation[0] == 0x69)
        return np.array(spectrum)

    def setIntegrationTime(self, timeInMs):
        """ Set the integration time in an integer value of milliseconds 
        for a spectrum. If the value is smaller than 3 ms, it will be unchanged.
        """
        hi = timeInMs // 256
        lo = timeInMs % 256        
        self.epCommandOut.write([0x02, lo, hi])

    def getIntegrationTime(self):
        """ Get the integration time in as an integer value in milliseconds
        """
        status = self.getStatus()
        return status.integrationTime


class USB4000(OISpectrometer):
    """
    A USB4000 spectrometer.  The main differences:
    1. The idProduct is 0x1022
    2. The integration time is 16-bit
    3. The format of the retrieved data is different for each spectrometer.

    """
    idProduct = 0x1022
    def __init__(self):
        OISpectrometer.__init__(self, idProduct=USB4000.idProduct, model="USB4000")
        self.epCommandOut = self.outputEndpoints[0]
        self.epMainIn = self.inputEndpoints[2]
        self.epSecondaryIn = self.inputEndpoints[1]
        self.epSecondaryIn = self.inputEndpoints[1]
        self.discardLeadingSamples = 5
        self.discardTrailingSamples = 173
        self.initializeDevice()

    def getSpectrumData(self):
        """ Retrieve the spectral data.  You must call requestSpectrum first.
        If the spectrum is not ready yet, it will simply wait. The timeout 
        is set short so it may timeout.  You would normally check with
        isSpectrumReady before calling this function.

        The format for the USB4000 is 512 bytes of integers in each packet

        Returns
        -------
        spectrum : np.array(float)
            The spectrum, in 16-bit integers corresponding to each wavelength
            available in self.wavelength.
        """
        spectrum = []
        buffer = array.array('B',[0]*512)

        if not self.lastStatus.isHighSpeed:
            raise NotImplementedError('Full speed mode not implemented for USB4000.')

        packetCount = self.lastStatus.packetCount
        exposureTime = self.lastStatus.integrationTime

        for packet in range(packetCount):
            inputEndpoint = self.inputEndpoints[0]
            if packet <= 3:
                inputEndpoint = self.inputEndpoints[1]

            buffer = inputEndpoint.read(size_or_buffer=512, timeout=exposureTime*2)
            values = unpack('<'+'H'*256, buffer)
            spectrum.extend(np.array(values))

        confirmation = self.inputEndpoints[0].read(size_or_buffer=1, timeout=200)
        if confirmation[0] != 0x69:
            self.flushEndpoints()
            raise RuntimeError('Spectrometer is desynchronized. Should disconnect')

        if self.discardTrailingSamples > 0:
            spectrum = spectrum[:-self.discardTrailingSamples]
        if self.discardLeadingSamples > 0:
            spectrum = spectrum[self.discardLeadingSamples:]

        return np.array(spectrum)

    def getStatus(self):
        """ The status of the spectrometer returned as a Status named tuple.

        Returns
        -------
        status : Status 
            You can access the fields of the status by index (i.e. status[0]) or
            via their names. See the `Status` class.

            pixels : int = None
            integrationTime: int = None
            isLampEnabled : bool = None
            triggerMode : int = None
            isSpectrumRequested: bool = None
            timerSwap: bool = None
            isSpectralDataReady : bool = None

        """
        self.epCommandOut.write(b'\xfe')
        parameters = array.array('B',[0]*self.inputEndpoints[2].wMaxPacketSize)
        nReadBytes = self.inputEndpoints[2].read(size_or_buffer=parameters, timeout=1000)

        statusList = unpack('<hL?BBB?Bxx?x',parameters[:16])
        status = StatusUSB4000(*statusList)
        self.lastStatus = status
        return status

    def setIntegrationTime(self, timeInMs):
        """ Set the integration time in an integer value of milliseconds 
        for a spectrum. If the value is smaller than 3 ms, it will be unchanged.
        """
        command = bytearray()
        command += b'\x02'
        command += pack('<L',int(timeInMs*1000))
        self.epCommandOut.write(command)

    def getIntegrationTime(self):
        """ Get the integration time in as an integer value in microseconds,
        then convert to lfoat in milliseconds
        """
        status = self.getStatus()
        return float(status.integrationTime)/1000

    def getParameter(self, index):
        """ Get any of the 20 parameters hardcoded into the spectrometer.

        Parameters
        ----------

        index: int
            0 – Serial Number
            1 – 0th order Wavelength Calibration Coefficient
            2 – 1st order Wavelength Calibration Coefficient
            3 – 2nd order Wavelength Calibration Coefficient
            4 – 3rd order Wavelength Calibration Coefficient
            5 – Stray light constant
            6 – 0th order non-linearity correction coefficient
            7 – 1st order non-linearity correction coefficient
            8 – 2nd order non-linearity correction coefficient
            9 – 3rd order non-linearity correction coefficient
            10 – 4th order non-linearity correction coefficient
            11 – 5th order non-linearity correction coefficient
            12 – 6th order non-linearity correction coefficient
            13 – 7th order non-linearity correction coefficient
            14 – Polynomial order of non-linearity calibration
            15 – Optical bench configuration: gg fff sss gg – Grating #, fff – filter wavelength, sss – slit size
            16 - USB2000 configuration: AWL V
                A – Array coating Mfg,
                W – Array wavelength (VIS, UV, OFLV),
                L – L2 lens installed,
                V – CPLD Version
            17 – Reserved
            18 – Reserved
            19 – Reserved

        Returns
        -------
        parameter : str
            The value of the parameter as an ASCII string
        """
        try:
            self.epCommandOut.write([0x05, index])

            parameters = array.array('B',[0]*self.inputEndpoints[2].wMaxPacketSize)
            self.inputEndpoints[2].read(size_or_buffer=parameters, timeout=200)
            for i, c in enumerate(parameters):
                if c == 0:
                    parameters = parameters[:i]
                    break
            return bytes(parameters[2:]).decode()

        except:
            self.flushEndpoints()
            raise RuntimeError('Reset attempted')


    def isSpectrumRequested(self) -> bool:
        """ The spectrometer is currently waiting for an acquisition to
        complete and will raise the ready flag when the spectrum is ready
        to be retrieved.

        Returns
        -------
        isSpectrumRequested : bool
            Whether or not the spectrometer is waiting for an acquisition
        """
        while True:
            status = self.getStatus()
            if status.acquisitionStatus & 2 != 0:
                break

        return True

    def isSpectrumReady(self):
        """ The requested spectrum is ready to be retrieved with getSpectrumData.

        Returns
        -------
        isSpectrumReady : bool
            Whether or not the spectrum ready to be retrieved
        """
        # return True

        while True:
            try:
                status = self.getStatus()
                if status.acquisitionStatus & 4 != 0:
                    break
            except:
                return False

        return True

class SpectraViewer:
    def __init__(self, spectrometer):
        """ A matplotlib-based window to display and manage a spectrometer
        to replace the insanely inept OceanView software from OceanInsight.
        If anybody reads this from Ocean Insight, you can take direct people
        to this Python script.  It is simpler to call it directly from the
        spectrometer object with its own display function that will instantiate
        a SpectraViewer and call its display function with itself as a paramater.
        There are now attributes of interest to a user.

        Parameters
        ----------

        spectrometer: OISpectrometer
            A spectrometer from Ocean Insight (for now, only USB2000)
        """

        self.spectrometer = spectrometer
        self.lastSpectrum = []
        self.figure = None
        self.axes = None
        self.quitFlag = False
        self.saveBtn = None
        self.integrationTimeBox = None
        self.animation = None

    def display(self):
        """ Display the spectrum in free-running mode, with simple
        autoscale, save and quit buttons as well as a text entry for
        the integration time. This is the only user-facing function that 
        is needed.
        """
        self.figure, self.axes = self.createFigure()

        axScale = plt.axes([0.12, 0.90, 0.15, 0.075])
        axSave = plt.axes([0.7, 0.90, 0.1, 0.075])
        axQuit = plt.axes([0.81, 0.90, 0.1, 0.075])
        axTime = plt.axes([0.59, 0.90, 0.1, 0.075])
        self.saveBtn = Button(axSave, 'Save')
        self.saveBtn.on_clicked(self.clickSave)
        quitBtn = Button(axQuit, 'Quit')
        quitBtn.on_clicked(self.clickQuit)
        autoscaleBtn = Button(axScale, 'Autoscale')
        autoscaleBtn.on_clicked(self.clickAutoscale)

        currentIntegrationTime = self.spectrometer.getIntegrationTime()
        self.integrationTimeBox = TextBox(axTime, 'Integration time [ms]',
                                          initial="{0}".format(currentIntegrationTime),
                                          label_pad=0.1)
        self.integrationTimeBox.on_submit(self.submitTime)
        self.figure.canvas.mpl_connect('key_press_event', self.keyPress)

        self.quitFlag = False
        self.animation = animation.FuncAnimation(self.figure, self.animate, interval=25)
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
        fig.canvas.set_window_title('Ocean Insight Spectrometer [serial # {0}, model {1}]'.format(serialNumber, model))
        axes.set_xlabel("Wavelength [nm]")
        axes.set_ylabel("Intensity [arb.u]")
        return fig, axes

    def plotSpectrum(self, spectrum=None):
        """ Plot a spectrum into the figure or request a new spectrum. This
        is called repeatedly when the display function is called."""
        try:
            if spectrum is None:
                spectrum = self.spectrometer.getSpectrum()

            if len(self.axes.lines) == 0:
                self.axes.plot(self.spectrometer.wavelength, spectrum, 'k')
                self.axes.set_xlabel("Wavelength [nm]")
                self.axes.set_ylabel("Intensity [arb.u]")
            else: 
                self.axes.lines[0].set_data( self.spectrometer.wavelength, spectrum) # set plot data
                self.axes.relim()
        except:
            pass

    def animate(self, i):
        """ Internal function that is called repeatedly to manage the
        update  of the spectrum plot. It is better to use the `animation`
        strategy instead of a loop with  plt.pause() because plt.pause() will
        always bring the window to the  foreground. 

        This function is also responsible for determing if the user asked to quit. 
        """
        if self.quitFlag:
            self.animation.event_source.stop()
            self.animation = None
            plt.close()

        self.lastSpectrum = self.spectrometer.getSpectrum()
        self.plotSpectrum(spectrum=self.lastSpectrum)

    def keyPress(self, event):
        """ Event-handling function for keypress: if the user clicks command-Q
        on macOS, it will nicely quit."""

        if event.key == 'cmd+q':
            self.clickQuit(event)

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
the text "{0}" converts to 0.  Use a valid value (≥3).')
            self.spectrometer.setIntegrationTime(time)
            plt.pause(0.3)
            self.axes.autoscale_view()
        except Exception as err:
            print("Error when setting integration time: ",err)
            self.integrationTimeBox.set_val("3")

    def clickAutoscale(self, event):
        """ Event-handling function to autoscale the plot """
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
            self.spectrometer.saveSpectrum(filepath, spectrum=self.lastSpectrum)

        self.animation.event_source.start()

    def clickQuit(self, event):
        """ Event-handling function to quit nicely."""

        self.quitFlag = True

if __name__ == "__main__":
    try:
        spectrometer = OISpectrometer.any()
        spectrometer.getSpectrum()
        spectrometer.display()
    except Exception as err:
        """ Something unexpected occurred, which is probably a module not available.
        We show some help.
        """
        OISpectrometer.showHelp(err)
