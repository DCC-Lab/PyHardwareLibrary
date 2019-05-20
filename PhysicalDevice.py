from enum import Enum
import typing
import numpy as np

class DeviceState(Enum):
    Unconfigured = 0 # Dont know anything
    Ready = 1        # Connected and initialized
    Recognized = 2   # Initialization has succeeded, but currently shutdown
    Unrecognized = 3 # Initialization failed

class PhysicalDevice:

    def __init__(serialNumber:str, productId:np.uint32, vendorId:np.uint32):
        self.vendorId = vendorId
        self.productId = productId
        self.serialNumber = serialNumber
        self.state = DeviceState.Unconfigured

    def initializeDevice():
        if self.state != DeviceState.Ready:
            try:
                self.doInitializeDevice()
                self.state = DeviceState.Ready
            except:
                self.state = DeviceState.Unrecognized

    def doInitializeDevice():
        return

    def shutdownDevice():
        if self.state == DeviceState.Ready:
            try:
                self.doShutdownDevice()
                self.state = DeviceState.Recognized
            except error:
                raise error

    def doShutdownDevice():
        return
