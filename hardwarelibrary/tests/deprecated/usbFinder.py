import usb.backend.libusb1 as libusb1
import usb.util

backend = libusb1.get_backend()
if backend is None:
    raise ValueError('No backend available')

for bus in usb.busses():
    print(bus)
    for device in bus.devices:
        if device != None:
            usbDevice = usb.core.find(idVendor=device.idVendor, 
                                      idProduct=device.idProduct)
            print(usbDevice)

