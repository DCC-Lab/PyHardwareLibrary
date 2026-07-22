from hardwarelibrary.physicaldevice import PhysicalDevice


class PowerStripDevice(PhysicalDevice):
    # A thin marker base for controllable power strips (switched outlets). The
    # behavior comes from the *Capability mixins a driver combines with it;
    # capability introspection (capabilities() / hasCapability()) is inherited
    # from PhysicalDevice.
    pass
