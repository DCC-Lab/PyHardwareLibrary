from enum import Enum
import typing
import numpy as np

class DeviceState(Enum):
    Unconfigured = 0 # Dont know anything
    Ready = 1        # Connected and initialized
    Recognized = 2   # Initialization has succeeded, but currently shutdown
    Unrecognized = 3 # Initialization failed

class PhysicalDeviceUnableToInitialize(Exception):
    pass

class PhysicalDevice:

    def __init__(self, serialNumber:str, productId:np.uint32, vendorId:np.uint32):
        self.vendorId = vendorId
        self.productId = productId
        self.serialNumber = serialNumber
        self.state = DeviceState.Unconfigured

    def initializeDevice(self):
        if self.state != DeviceState.Ready:
            try:
                self.doInitializeDevice()
                self.state = DeviceState.Ready
            except Exception as error:
                self.state = DeviceState.Unrecognized
                raise error

    def doInitializeDevice(self):
        raise NotImplementedError("Base class must override doInitializeDevice()")

    def shutdownDevice(self):
        if self.state == DeviceState.Ready:
            try:
                self.doShutdownDevice()
            except Exception as error:
                raise error
            finally:
                self.state = DeviceState.Recognized

    def doShutdownDevice(self):
        raise NotImplementedError("Base class must override doShutdownDevice()")
