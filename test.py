from hardwarelibrary.spectrometers import getAllSubclasses, Spectrometer

devices = getAllSubclasses(Spectrometer)
for dev in devices:
    print("{0}".format(dev))
