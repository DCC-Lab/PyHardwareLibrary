from hardwarelibrary.spectrometers import OISpectrometer
from typing import NamedTuple
import numpy as np
import struct

class SAS(OISpectrometer):
    """
    A USB2000 spectrometer.  The main differences:
    1. The idProduct is 0x1002
    2. The integration time is 16-bit
    3. The format of the retrieved data is different for each spectrometer.

    """

    classIdProduct = 0x1006

    statusPackingFormat = '>hh?B???xxxxxxx'
    class Status(NamedTuple):
        """
        Status of the Ocean Insight USB2000 spectrometer. NamedTuple are compatible
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

    def __init__(self, serialNumber=None, idProduct=None, idVendor=None):
        OISpectrometer.__init__(self, serialNumber, idProduct, idVendor, model="SAS")
        self.epCommandOutIdx = 0
        self.epMainInIdx = 0
        self.epSecondaryInIdx = 1

        self.epParametersIdx = 1
        self.epStatusIdx = 1

        # self.epParametersIdx = self.epSecondaryInIdx
        # self.epStatusIdx = self.epMainInIdx

    def doInitializeDevice(self):
        """
        Nothing particular to do, but making it explicit
        """
        super().doInitializeDevice()

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
            bytesRead = self.epMainIn.read(size_or_buffer=64, timeout=200)
            print(packet, bytesRead)
            data = struct.unpack("<"+"H"*32, bytesRead)
            # bytesReadHi = self.epMainIn.read(size_or_buffer=64, timeout=200)
            
            spectrum.extend(data)


        confirmation = self.epMainIn.read(size_or_buffer=1, timeout=200)
        spectrum[0] = spectrum[1]

        assert(confirmation[0] == 0x69)
        return np.array(spectrum)

    def setIntegrationTime(self, timeInMs):
        """ Set the integration time in an integer value of milliseconds 
        for a spectrum. If the value is smaller than 3 ms, it will be unchanged.
        """
        self.sendCommand(cmdBytes = b'\x02',
                         payloadBytes = pack('<L',int(timeInMs)))
        # self.sendCommand(cmdBytes = b'\x02',
        #                  payloadBytes = pack('<L',int(timeInMs*self.timeScale)))


if __name__ == "__main__":
    s = SAS()
    s.initializeDevice()

    print(s.inputEndpoints)
    print(s.outputEndpoints)
    # s.requestSpectrum()
    # while not s.isSpectrumReady():
    #     pass

    # while True:
    print(s.getSpectrum())
    # s.display()