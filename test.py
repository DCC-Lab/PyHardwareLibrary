from hardwarelibrary import DeviceManager

dm = DeviceManager()
devices = dm.updateConnectedDevices()
spectro = dm.anySpectrometerDevice()
spectro.display()