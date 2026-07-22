from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.powerstrips.capabilities import Capability


class PowerStripDevice(PhysicalDevice):
    """Family marker base for controllable power strips (switched outlets).

    A driver subclasses this and mixes in the capability classes from
    capabilities.py (OutletSwitchingControl, DefaultOutletControl,
    CurrentMeteringControl). The behaviour lives in the mixins; this base only
    reports which capabilities a given driver actually implements.
    """

    def capabilities(self) -> list:
        # The capability mixins, not the marker nor the device class itself
        # (a driver is a Capability subclass too, but it is a PhysicalDevice).
        return [klass for klass in type(self).__mro__
                if issubclass(klass, Capability)
                and klass is not Capability
                and not issubclass(klass, PhysicalDevice)]

    def hasCapability(self, capabilityClass) -> bool:
        return isinstance(self, capabilityClass)
