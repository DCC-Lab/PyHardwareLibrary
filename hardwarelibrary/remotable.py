"""Remotable: capability that lets a PhysicalDevice serve itself over Pyro5.

PhysicalDevice mixes this in, so *every* device is remotable. The mixin exposes
generic Pyro dispatchers -- callMethod() / getAttribute() -- that forward to the
real device. There is no per-method @expose (sidestepping the
@expose-does-not-inherit gotcha) and no servant wrapping the device; the client
drives everything through one generic ProxyDevice handle. Device events are
delivered separately, by the DistributedNotificationCenter; the helpers here
(resolveNotificationName / _allNotificationMembers / _coercePayload) support it.

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


def _allEnumSubclasses(root=Enum):
    for subclass in root.__subclasses__():
        yield subclass
        yield from _allEnumSubclasses(subclass)


def _allNotificationMembers():
    for enumClass in _allEnumSubclasses():
        if "Notification" in enumClass.__name__:
            yield from enumClass


def resolveNotificationName(name):
    """Map a notification name string (e.g. 'didMove') back to its Enum member.

    NotificationCenter keys observers by Enum, but only a primitive name can cross
    the wire. Notification enums (named '*Notification') are discovered among the
    imported Enum subclasses, so no family has to be hard-coded here.
    """
    for member in _allNotificationMembers():
        if member.name == name or member.value == name:
            return member
    raise ValueError(f"Unknown notification name '{name}'")


def _coercePayload(value):
    # serpent flattens tuples to lists anyway; make it explicit and recurse.
    if isinstance(value, (tuple, list)):
        return [_coercePayload(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


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
