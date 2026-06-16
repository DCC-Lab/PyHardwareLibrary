"""Optional remoting layer: host a PhysicalDevice in its own process or machine.

A device becomes remotable by mixing in `Remotable` (PhysicalDevice already does),
so it serves itself over Pyro5. Callers obtain a handle with
`createDevice(..., isolated=True)` or `launchIsolatedDevice(...)`, which returns a
single generic `ProxyDevice` that forwards every call automatically -- no
per-device proxy class. Running the device in a separate, supervised process means
a buggy third-party driver can crash its own process without taking down the app.

Device events are delivered through `DistributedNotificationCenter`, a Pyro-based
cross-process NotificationCenter: observe a remote device with the same
addObserver(...) call you would use locally.

This is an *additive* transport; the same Pyro5 machinery extends to cross-machine
control later. This prototype is same-machine only (Pyro5 over localhost; the
event broker runs on localhost rather than being discovered via a name server).

Requires the optional `Pyro5` dependency (`pip install hardwarelibrary[remote]`).
"""
from hardwarelibrary.remoting.isolation import createDevice, launchIsolatedDevice
from hardwarelibrary.remoting.deviceproxy import ProxyDevice, IsolatedDeviceError
from hardwarelibrary.remoting.distributednotificationcenter import DistributedNotificationCenter
from hardwarelibrary.remotable import Remotable

__all__ = [
    "createDevice",
    "launchIsolatedDevice",
    "ProxyDevice",
    "Remotable",
    "IsolatedDeviceError",
    "DistributedNotificationCenter",
]
