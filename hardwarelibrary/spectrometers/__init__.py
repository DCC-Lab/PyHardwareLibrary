__all__ = ["oceaninsight"]

import os 
from pathlib import *

rootHardwareLibrary = Path(os.path.abspath(__file__)).parents[1]
stellarEncrypted = rootHardwareLibrary.joinpath('spectrometers/stellarnet.zip')
stellarDecrypted = rootHardwareLibrary.joinpath('spectrometers/stellarnet.py')

if os.path.exists(stellarEncrypted) and not os.path.exists(stellarDecrypted):
    print("The StellarNet software requires a password. Please contact StellarNet if you would like to use it.")
    print("Then, run `python3 -m hardwarelibrary --stellar` and enter the password when prompted.")
    print("Make sure you extract the files in the spectrometers/ directory of hardwarelibrary, where the zip file is.")

if not os.path.exists(stellarDecrypted):
    class StellarNet:
        def __init__(self):
            print("The StellarNet module must be licenced and decrypted by StellarNet. Please contact them for info.")
            print("If you have the password, run `python -m hardwarelibrary --stellar` and enter it at the prompt. Do not distribute.")
            print("Make sure you extract the files in the spectrometers/ directory of hardwarelibrary, where the zip file is.")
else:            
    from .stellarnet import StellarNet

from .oceaninsight import OISpectrometer, USB2000, USB4000
from .viewer import SpectraViewer

def any() -> OISpectrometer:
    return OISpectrometer.any()

def connectedUSBDevices(idProduct=None, serialNumber=None):
    return OISpectrometer.connectedUSBDevices(idProduct=idProduct, serialNumber=serialNumber)

def matchUniqueUSBDevice(idProduct=None, serialNumber=None):
    return OISpectrometer.matchUniqueUSBDevice(idProduct=idProduct, serialNumber=serialNumber)

