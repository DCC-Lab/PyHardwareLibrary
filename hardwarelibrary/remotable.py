"""Remotable: capability that lets a PhysicalDevice serve itself over Pyro5.

PhysicalDevice mixes this in, so *every* device is remotable. The mixin exposes
two generic Pyro dispatchers -- callMethod() and getAttribute() -- that forward to
the real device, so there is no per-method @expose (sidestepping the
@expose-does-not-inherit gotcha) and no servant wrapping the device. The client
drives these through one generic ProxyDevice handle.

Pyro5 is an OPTIONAL dependency. This module must import with or without it: when
Pyro5 is absent, `expose` is a no-op, so the methods exist but the device simply
cannot be served (importing the library never requires Pyro5).
"""
from enum import Enum

try:
    from Pyro5.api import expose as _expose
except Exception:  # Pyro5 not installed: exposure is a no-op
    def _expose(member):
        return member


class Remotable:
    @_expose
    def callMethod(self, methodName, *args, **kwargs):
        # One exposed entry point forwards the whole public API. Block private
        # names so a remote caller cannot reach internals.
        if methodName.startswith("_"):
            raise PermissionError(f"'{methodName}' is not remotely callable")
        return getattr(self, methodName)(*args, **kwargs)

    @_expose
    def getAttribute(self, name):
        if name.startswith("_"):
            raise PermissionError(f"'{name}' is not remotely readable")
        value = getattr(self, name)
        # Send enums (e.g. DeviceState) as their primitive value; the client
        # rebuilds the enum so no custom type has to cross the serpent boundary.
        if isinstance(value, Enum):
            return value.value
        return value
