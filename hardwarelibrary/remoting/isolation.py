import json
import select
import subprocess
import sys
import time

import Pyro5.api

from hardwarelibrary.remoting.deviceproxy import ProxyDevice, IsolatedDeviceError


def createDevice(deviceClass, *, isolated=False, **kwargs):
    """Create a device either in this process or in its own supervised process.

    ``isolated=False`` returns the real device (in-process, direct, fast) -- a
    genuine instance of deviceClass, so isinstance against its family ABC holds.
    ``isolated=True`` returns a ProxyDevice handle to the same device running in a
    separate process, so a crash in a (possibly buggy) driver cannot take down
    this process. Both are driven by the same method calls.
    """
    if not isolated:
        return deviceClass(**kwargs)
    return launchIsolatedDevice(deviceClass, **kwargs)


def launchIsolatedDevice(deviceClass, *, startupTimeout=15.0, **kwargs):
    """Spawn a host process for deviceClass and return a ProxyDevice for it.

    deviceClass must mix in Remotable so it can serve itself over Pyro5.
    """
    classPath = f"{deviceClass.__module__}.{deviceClass.__qualname__}"
    process = subprocess.Popen(
        [sys.executable, "-m", "hardwarelibrary.remoting.devicehost",
         "--device-class", classPath, "--kwargs", json.dumps(kwargs)],
        stdout=subprocess.PIPE, text=True,
    )
    uri = _awaitReady(process, startupTimeout)
    proxy = Pyro5.api.Proxy(uri)
    return ProxyDevice(proxy, process)


def _awaitReady(process, timeout):
    """Read the host's stdout until it prints 'READY <uri>', or fail/time out."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process.kill()
            raise IsolatedDeviceError("timed out waiting for device host to start")
        readable, _, _ = select.select([process.stdout], [], [], remaining)
        if not readable:
            continue
        line = process.stdout.readline()
        if line == "":  # EOF: the host exited before becoming ready
            raise IsolatedDeviceError(
                f"device host exited before ready (exit code {process.poll()})")
        line = line.strip()
        if line.startswith("READY "):
            return line[len("READY "):]
