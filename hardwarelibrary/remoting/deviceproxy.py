import Pyro5.api
import Pyro5.errors

from hardwarelibrary.physicaldevice import DeviceState


class IsolatedDeviceError(RuntimeError):
    """Raised when the process hosting a remote device has died or is unreachable."""


class ProxyDevice:
    """One generic, duck-typed handle to a Remotable device elsewhere.

    Every method call is forwarded to the remote device automatically -- there is
    no per-method or per-device code, and no class mirrors the device's API. The
    common PhysicalDevice attributes are read live from the remote so they never
    go stale. When the device runs in a child process, the handle also supervises
    it: a dead host raises IsolatedDeviceError instead of hanging or crashing the
    caller.

    The handle is intentionally not an instance of the device's family ABC; use
    it by calling its methods (duck typing), not isinstance.
    """

    def __init__(self, pyroProxy, process=None):
        # Set via object.__setattr__ so they are not seen as remote attributes.
        object.__setattr__(self, "_pyro", pyroProxy)
        object.__setattr__(self, "_process", process)
        object.__setattr__(self, "_deviceId", str(pyroProxy._pyroUri))

    # -- host-process supervision -------------------------------------------
    def isAlive(self):
        return self._process is None or self._process.poll() is None

    @property
    def processId(self):
        return None if self._process is None else self._process.pid

    def _invoke(self, thunk):
        if not self.isAlive():
            raise IsolatedDeviceError(
                f"device process is not running (exit code {self._process.poll()})")
        try:
            # A Pyro proxy is bound to one thread; let whichever thread drives the
            # device (e.g. a command thread, or a notification handler) use it.
            self._pyro._pyroClaimOwnership()
            return thunk()
        except Pyro5.errors.CommunicationError as error:
            if self._process is not None and self._process.poll() is not None:
                raise IsolatedDeviceError(
                    f"device process died (exit code {self._process.poll()})") from error
            raise

    def _call(self, methodName, *args, **kwargs):
        return self._invoke(lambda: self._pyro.callMethod(methodName, *args, **kwargs))

    def _get(self, name):
        return self._invoke(lambda: self._pyro.getAttribute(name))

    # -- common PhysicalDevice attributes (shared by every device) ----------
    @property
    def state(self):
        return DeviceState(self._get("state"))

    @property
    def serialNumber(self):
        return self._get("serialNumber")

    @property
    def idVendor(self):
        return self._get("idVendor")

    @property
    def idProduct(self):
        return self._get("idProduct")

    # Events are delivered out-of-band by the DistributedNotificationCenter, keyed
    # on this device's id; observe a remote device exactly like a local one:
    #   DistributedNotificationCenter().addObserver(
    #       self.onMove, LinearMotionNotification.didMove, observedObject=stage)

    # -- everything else forwards automatically -----------------------------
    def __getattr__(self, name):
        # Reached only for names not defined on this class (moveTo, home, ...).
        if name.startswith("_"):
            raise AttributeError(name)
        def forward(*args, **kwargs):
            return self._call(name, *args, **kwargs)
        return forward

    # -- lifecycle of the host process --------------------------------------
    def shutdownProcess(self, timeout=5.0):
        """Shut the device down cleanly (best effort) and stop its host process."""
        if self.isAlive():
            try:
                self._call("shutdownDevice")
            except Exception:
                pass
        try:
            self._pyro._pyroRelease()
        except Exception:
            pass
        if self._process is not None and self.isAlive():
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout)
            except Exception:
                self._process.kill()
