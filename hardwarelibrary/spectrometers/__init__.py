import os 
from pathlib import *

rootHardwareLibrary = Path(os.path.abspath(__file__)).parents[1]
candidates = [rootHardwareLibrary.joinpath('communication/libusb/MS64/libusb-1.0.dll'),
                 rootHardwareLibrary.joinpath('communication/libusb/MS32/libusb-1.0.dll')]

stellarEncrypted = rootHardwareLibrary.joinpath('spectrometers/stellarnet.zip')

if os.path.exists(stellarEncrypted):
    print("The StellarNet software requires a password. Please contact StellarNet if you would like to use it.")
    print("Then, run `python3 -m hardwarelibrary -stellar` and enter the password when prompted.")

__all__ = ["oceaninsight"]

from .oceaninsight import OISpectrometer, USB2000, USB4000, SpectraViewer

def any() -> OISpectrometer:
    return OISpectrometer.any()

def connectedUSBDevices(idProduct=None, serialNumber=None):
    return OISpectrometer.connectedUSBDevices(idProduct=idProduct, serialNumber=serialNumber)

def matchUniqueUSBDevice(idProduct=None, serialNumber=None):
    return OISpectrometer.matchUniqueUSBDevice(idProduct=idProduct, serialNumber=serialNumber)

