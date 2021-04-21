import usb.core
import usb.util

for bus in usb.busses():
    for device in bus.devices:
        if device != None:
            usbDevice = usb.core.find(idVendor=device.idVendor, 
                                      idProduct=device.idProduct)
            print(usbDevice)


# device = usb.core.find(idVendor=0x0403, idProduct=0x6001)  
# if device is None:
# 	raise IOError("Can't find device")

# print(device)

# device.set_configuration()                        # Use the first configuration
# configuration = device.get_active_configuration() # Then get a reference to it
# print(configuration)