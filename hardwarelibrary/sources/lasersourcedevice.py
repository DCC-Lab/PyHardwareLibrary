from hardwarelibrary.physicaldevice import PhysicalDevice


class LaserSourceDevice(PhysicalDevice):
    # A thin marker base for laser sources. The behavior comes from the
    # *Capability mixins a driver combines with it; capability introspection
    # (capabilities() / hasCapability()) is inherited from PhysicalDevice.
    pass
