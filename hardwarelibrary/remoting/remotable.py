"""Remotable: capability mixin that lets a PhysicalDevice serve itself over Pyro5.

A device class becomes remotable simply by mixing this in::

    class SutterDevice(LinearMotionDevice, Remotable):
        ...

There is no separate servant wrapping the device and no per-class proxy mirroring
its API. The mixin exposes two generic dispatchers (callMethod / getAttribute)
that forward to the real device, and the client drives them through one generic
ProxyDevice handle.
"""
from enum import Enum

import Pyro5.api


class Remotable:
    @Pyro5.api.expose
    def callMethod(self, methodName, *args, **kwargs):
        # One exposed entry point forwards the whole public API. Block private
        # names so a remote caller cannot reach internals.
        if methodName.startswith("_"):
            raise PermissionError(f"'{methodName}' is not remotely callable")
        return getattr(self, methodName)(*args, **kwargs)

    @Pyro5.api.expose
    def getAttribute(self, name):
        if name.startswith("_"):
            raise PermissionError(f"'{name}' is not remotely readable")
        value = getattr(self, name)
        # Send enums (e.g. DeviceState) as their primitive value; the client
        # rebuilds the enum so no custom type has to cross the serpent boundary.
        if isinstance(value, Enum):
            return value.value
        return value
