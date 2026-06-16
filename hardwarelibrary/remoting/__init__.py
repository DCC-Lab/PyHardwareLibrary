"""Optional remoting layer: host a PhysicalDevice in its own process.

This is an *additive* transport. A device can run in-process (direct, fast) or in
a separate, supervised process reached through a same-interface proxy, so a buggy
third-party driver can crash its own process without taking down the application.

The same Pyro5 machinery extends to cross-machine control later; this prototype is
same-machine only (Pyro5 over localhost, no name server).

Requires the optional `Pyro5` dependency (`pip install hardwarelibrary[remote]`).
"""
from hardwarelibrary.remoting.isolation import createDevice, launchIsolatedDevice
from hardwarelibrary.remoting.deviceproxy import RemoteDevice, IsolatedDeviceError

__all__ = [
    "createDevice",
    "launchIsolatedDevice",
    "RemoteDevice",
    "IsolatedDeviceError",
]
