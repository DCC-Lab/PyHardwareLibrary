from hardwarelibrary.motion import SutterDevice
import time

device = SutterDevice(serialNumber="debug")
nbDonnees = 5
dist = 1000

for i in range(nbDonnees+1):
    if i == 0:
        #device.home()
        device.work()
        print(device.position())
        time.sleep(1)
    if i % 2 == 0:
        fac = 1
    else:
        fac = -1
    for ii in range(nbDonnees+1):
        if ii != nbDonnees:
            device.moveBy((dist*fac, 0, 0))
        else:
            device.moveBy((0, dist, 0))
        print(device.position())
        time.sleep(1)
