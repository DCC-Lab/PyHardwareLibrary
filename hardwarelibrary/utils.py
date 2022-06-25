
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
