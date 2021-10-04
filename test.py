from hardwarelibrary import DeviceManager

dm = DeviceManager()
devices = dm.updateConnectedDevices()
spectro = devices[0]
spectro.display()