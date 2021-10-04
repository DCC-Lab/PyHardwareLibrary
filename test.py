from hardwarelibrary import DeviceManager

dm = DeviceManager()
devices = dm.updateConnectedDevices()
print(dm.anyPowerMeterDevice())
# spectro = dm.anySpectrometerDevice()
# spectro.display()