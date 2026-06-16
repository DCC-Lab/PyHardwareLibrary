import Pyro5.api

from hardwarelibrary.motion.linearmotiondevice import LinearMotionDevice

# Methods that are safe to invoke remotely, by device family. One generic
# dispatcher (callMethod) exposes the whole rich API while this whitelist blocks
# arbitrary remote attribute access. Extend FAMILY_METHODS as families are added.
LIFECYCLE_METHODS = {"initializeDevice", "shutdownDevice"}
FAMILY_METHODS = {
    LinearMotionDevice: {
        "moveTo", "moveBy", "position", "home",
        "moveInMicronsTo", "moveInMicronsBy", "positionInMicrons",
    },
}


@Pyro5.api.expose
class DeviceServant:
    """Wraps one PhysicalDevice; this is the object registered with the daemon.

    The device itself is never sent over the wire (it owns a port, an RLock and a
    monitoring thread, and is unpicklable). Only this servant is registered, and a
    single callMethod() dispatcher forwards whitelisted calls to the device.
    """

    def __init__(self, device):
        self.device = device
        self._allowedMethods = set(LIFECYCLE_METHODS)
        for family, methods in FAMILY_METHODS.items():
            if isinstance(device, family):
                self._allowedMethods |= methods

    def callMethod(self, methodName, *args, **kwargs):
        if methodName not in self._allowedMethods:
            raise PermissionError(f"Method '{methodName}' is not remotely callable")
        return getattr(self.device, methodName)(*args, **kwargs)

    def deviceType(self):
        return type(self.device).__name__

    def serialNumber(self):
        return self.device.serialNumber

    def idVendor(self):
        return self.device.idVendor

    def idProduct(self):
        return self.device.idProduct

    def stateValue(self):
        # DeviceState is an IntEnum; send the plain int and let the client rebuild
        # the enum, so no custom type has to cross the serpent boundary.
        return int(self.device.state)
