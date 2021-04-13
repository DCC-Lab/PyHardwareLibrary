__all__ = ["oceaninsight"]

from .oceaninsight import OISpectrometer, USB2000, USB4000, SpectraViewer

def any() -> OISpectrometer:
    return OISpectrometer.any()

def connectedDevices(idProduct=None, serialNumber=None):
    return OISpectrometer.connectedUSBDevices(idProduct=idProduct, serialNumber=serialNumber)

def matchUniqueDevice(idProduct=None, serialNumber=None):
    return OISpectrometer.matchUniqueUSBDevice(idProduct=idProduct, serialNumber=serialNumber)
