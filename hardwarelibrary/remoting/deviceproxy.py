import Pyro5.api
import Pyro5.errors

from hardwarelibrary.physicaldevice import DeviceState


class IsolatedDeviceError(RuntimeError):
    """Raised when the subprocess hosting a device has died or is unreachable."""


class RemoteDevice:
    """Client-side handle to a PhysicalDevice running in another process.

    Presents the same public interface as the device (moveTo/moveBy/position/home,
    initializeDevice/shutdownDevice, state, serialNumber, ...), so calling code is
    identical to driving the device in-process; only how you obtain the handle
    differs. If the host process dies, calls raise IsolatedDeviceError instead of
    taking down this process.
    """

    def __init__(self, proxy, process):
        # Set through object.__setattr__ so they don't route through __getattr__.
        object.__setattr__(self, "_proxy", proxy)
        object.__setattr__(self, "_process", process)

    # -- host-process supervision -------------------------------------------
    def isAlive(self):
        return self._process.poll() is None

    @property
    def processId(self):
        return self._process.pid

    def _guard(self):
        if not self.isAlive():
            raise IsolatedDeviceError(
                f"device process is not running (exit code {self._process.poll()})")

    def _invoke(self, thunk):
        self._guard()
        try:
            return thunk()
        except Pyro5.errors.CommunicationError as error:
            # A dropped connection most often means the host process just died.
            if not self.isAlive():
                raise IsolatedDeviceError(
                    f"device process died (exit code {self._process.poll()})") from error
            raise

    def _call(self, methodName, *args, **kwargs):
        return self._invoke(lambda: self._proxy.callMethod(methodName, *args, **kwargs))

    def _query(self, accessorName):
        return self._invoke(lambda: getattr(self._proxy, accessorName)())

    # -- device interface ----------------------------------------------------
    def position(self):
        # serpent turns tuples into lists on the wire; restore the tuple.
        return tuple(self._call("position"))

    def positionInMicrons(self):
        return tuple(self._call("positionInMicrons"))

    @property
    def state(self):
        return DeviceState(self._query("stateValue"))

    @property
    def serialNumber(self):
        return self._query("serialNumber")

    @property
    def idVendor(self):
        return self._query("idVendor")

    @property
    def idProduct(self):
        return self._query("idProduct")

    def __getattr__(self, name):
        # Reached only for names not defined on the class (e.g. moveTo, moveBy,
        # home, initializeDevice): forward them through the remote dispatcher.
        if name.startswith("_"):
            raise AttributeError(name)
        def remoteCall(*args, **kwargs):
            return self._call(name, *args, **kwargs)
        return remoteCall

    # -- lifecycle of the host process --------------------------------------
    def shutdownProcess(self, timeout=5.0):
        """Shut the device down cleanly (best effort) and stop its host process."""
        if self.isAlive():
            try:
                self._call("shutdownDevice")
            except Exception:
                pass
        try:
            self._proxy._pyroRelease()
        except Exception:
            pass
        if self.isAlive():
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout)
            except Exception:
                self._process.kill()
