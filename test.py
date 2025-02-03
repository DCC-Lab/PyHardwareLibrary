#from hardwarelibrary.spectrometers import getAllSubclasses, Spectrometer

#devices = getAllSubclasses(Spectrometer)
#for dev in devices:
#    print("{0}".format(dev))

from hardwarelibrary.spectrometers.oceaninsight import DebugSpectro

s = DebugSpectro()
s.display()
