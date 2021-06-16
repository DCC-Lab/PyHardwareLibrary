from hardwarelibrary.motion import SutterDevice

device = SutterDevice(serialNumber="debug")
nbDonnees = 5
dist = 1000

for i in range(nbDonnees+1):
    if i == 0:
        #Move to home position before moving to work position
        commandBytes = pack('<cc', b'H', b'\r')
        device.port.write(commandBytes)
        device.port.read(1)
        #move to work position
        commandBytes = pack('<cc', b'Y', b'\r')
        device.port.write(commandBytes)
        device.port.read(1)
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
        device.port.read(1)
        print(device.position())
        time.sleep(1)
