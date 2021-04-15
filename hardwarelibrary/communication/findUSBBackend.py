import usb.backend.libusb1
from ctypes import c_void_p, c_int
from ctypes.util import find_library
import os
import platform
from pathlib import *
import usb.core

def validateUSBBackend():
    backend = usb.backend.libusb1.get_backend()
    if backend is not None:
        try:
            usb.core.find(backend=backend)
            return
        except:
            pass
 
    libusbPath = None

    if platform.system() == 'Windows':
        rootHardwareLibrary = PureWindowsPath(os.path.abspath(__file__)).parents[1]
        candidates = [rootHardwareLibrary.joinpath('communication/libusb/MS64/libusb-1.0.dll'),
                         rootHardwareLibrary.joinpath('communication/libusb/MS32/libusb-1.0.dll')]
    elif os.name() == 'Darwin':
        rootHardwareLibrary = PurePosixPath(os.path.abspath(__file__)).parents[1]
        candidates = [rootHardwareLibrary.joinpath('communication/libusb/Darwin/libusb-1.0.0.dylib')]
    else:
        print('Cannot validate libusb backend.')

    for libpath in candidates:
        if os.path.exists(libpath):
            backend = usb.backend.libusb1.get_backend(find_library=lambda x: "{0}".format(libpath))
            if backend is not None:
                try:
                    usb.core.find(backend=backend)
                    break
                except:
                    pass
        else:
            print("File does not exist {0}".format(libpath))


if __name__ == "__main__":
    validateUSBBackend()

