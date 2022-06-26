import hardwarelibrary.physicaldevice
import usb.util
import re

def getAllSubclasses(aClass):
    allSubclasses = []
    for subclass in aClass.__subclasses__():
        allSubclasses.append(subclass)
        if len(subclass.__subclasses__()) != 0:
            allSubclasses.extend(getAllSubclasses(subclass))

    return allSubclasses

def getAllDeviceClasses(aClass, abstractClasses=False, debugDevices=False):
    allPossibleSubClasses = getAllSubclasses(aClass)
    allDeviceClasses = []
    for aClass in allPossibleSubClasses:
        if aClass.classIdProduct is not None:
            if not debugDevices and aClass.isDebugClass():
                pass
            else:
                allDeviceClasses.append(aClass)
        elif abstractClasses:
            allDeviceClasses.append(aClass)

    return allDeviceClasses

def getAllUSBIds(aClass, debugDevices=False):
    classes = getAllDeviceClasses(aClass, abstractClasses=False, debugDevices=debugDevices)
    usbIds = []
    for aClass in classes:
        if aClass.classIdProduct is not None:
            usbIds.append((aClass.classIdVendor, aClass.classIdProduct))
        elif abstractClasses:
            usbIds.append((aClass.classIdVendor, aClass.classIdProduct))

    return usbIds

def getCandidateDeviceClasses(aClass, idVendor, idProduct):
    allClasses = getAllDeviceClasses(aClass)

    candidateClasses = []
    for aClass in allClasses:
        if aClass.isCompatibleWith(serialNumber="*", idProduct=idProduct, idVendor=idVendor):
            candidateClasses.append(aClass)

    return candidateClasses

def connectedUSBDevices(vidpids = None, serialNumberPattern=None):
    """
    Return a list of supported USB devices that are currently connected.
    If idProduct is provided, match only these products. If a serial
    number is provided, return the matching device otherwise return an
    empty list. If no serial number is provided, return all devices.

    Parameters
    ----------
    vidpid: list of (int, int) Default: None
        A tuple (idVendor, idProduct) to match
    serialNumber: str Default: None
        The serial number to match, when there are still more than one device after
        filtering out the idProduct.  If there is a single match, the serial number
        is disregarded.

    Returns
    -------

    devices: list of Device
        A list of connected devices matching the criteria provided
    """

    devices = []
    if vidpids is not None:
        for (idVendor, idProduct) in vidpids:
            devices.extend(list(usb.core.find(find_all=True, idVendor=idVendor, idProduct=idProduct)))
    else:
        devices.extend(list(usb.core.find(find_all=True)))

    if serialNumberPattern is not None: # A serial number was provided, try to match
        for device in devices:
            deviceSerialNumber = usb.util.get_string(device, device.iSerialNumber )
            if re.search(serialNumberPattern, deviceSerialNumber):
                return [device]

        return [] # Nothing matched

    return devices

def matchUniqueUSBDevice(vidpid = None, serialNumberPattern=None):
    """ A class method to find a unique device that matches the criteria provided. If there
    is a single device connected, then the default parameters will make it return
    that single device. The idProduct is used to filter out unwanted products. If
    there are still more than one of the same product type, then the serial number
    is used to separate them. If we can't find a unique device, we raise an
    exception to suggest what to do.

    Parameters
    ----------
    vidpid: (int,int) Default: None
        The USB idVendor, idProduct to match
    serialNumberPattern: str Default: None
        The serial number to match, when there are still more than one after
        filtering out the idVendor and idProduct.  if there is a single match, the serial number
        is disregarded.

    Returns
    -------

    device: Device
        A single device matching the criteria

    Raises
    ------
        RuntimeError if a single device cannot be found.
    """

    devices = connectedUSBDevices(vidpid=vidpid, serialNumberPattern=serialNumber)

    device = None
    if len(devices) == 1:
        device = devices[0] # only (len==1) or any (len>1 and serial None)
    elif len(devices) > 1:
        raise PhysicalDevice.TooManyPhysicalDevicesConnected('Several devices with the appropriate vid/pid were found, cannot select one from the list of devices {0}'.format(devices))
    else:
        raise PhysicalDevice.NoPhysicalDeviceConnected('Device with the appropriate idVendor and idProduct {0}, serial number ({1}) was not found in the list of devices {2}'.format( vidpid, serialNumber, devices))

    return device
