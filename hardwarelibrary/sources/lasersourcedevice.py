from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.sources.capabilities import Capability


class LaserSourceDevice(PhysicalDevice):
    def capabilities(self) -> list:
        # The capability mixins, not the marker nor the device class itself
        # (a driver is a Capability subclass too, but it is a PhysicalDevice).
        return [klass for klass in type(self).__mro__
                if issubclass(klass, Capability)
                and klass is not Capability
                and not issubclass(klass, PhysicalDevice)]

    def hasCapability(self, capabilityClass) -> bool:
        return isinstance(self, capabilityClass)
