from hardwarelibrary import DeviceManager
from hardwarelibrary import NotificationCenter
from hardwarelibrary import PhysicalDeviceNotification

class Observer:
	def print(self, notification):
		print(notification.userInfo)


dm = DeviceManager()
devices = dm.updateConnectedDevices()
meter = dm.anyPowerMeterDevice()
meter.initializeDevice()

observer = Observer()
NotificationCenter().addObserver(observer, 
	                             observer.print, 
	                             notificationName=PhysicalDeviceNotification.status,
	                             observedObject=meter)

meter.startBackgroundStatusUpdates()


# spectro = dm.anySpectrometerDevice()
# spectro.display()

