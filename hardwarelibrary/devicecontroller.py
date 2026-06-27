"""A headless, GUI-agnostic controller around any PhysicalDevice.

Building an interactive app (e.g. a GUI) on top of a PhysicalDevice means
solving the same problems every time:

  * device calls block (the Millennia eV confirms ON/OFF by writing, settling,
    and reading back -- up to several seconds), so they cannot run on a UI
    thread;
  * status polling and user actions both touch the same port, so they must be
    serialized to avoid interleaving bytes (writeCommand is not under the
    port's transactionLock);
  * connections drop -- the cable is pulled, the port disappears -- and the app
    wants to recover automatically;
  * none of this should know anything about the UI toolkit.

DeviceController owns a single worker thread through which *all* device access
flows -- submitted commands and the periodic status poll alike -- so there are
no races and ordering is preserved. It reports everything through the existing
NotificationCenter, so any front-end (Tk/mytk, Qt, a CLI, a test) just observes
notifications; marshalling them onto a UI thread is the front-end's job.

It is deliberately decoupled from any toolkit: this module imports only the
standard library and NotificationCenter.

Example::

    from hardwarelibrary.devicecontroller import (
        DeviceController, DeviceControllerNotification as N)
    from hardwarelibrary.notificationcenter import NotificationCenter
    from hardwarelibrary.sources.millennia import MillenniaDevice

    controller = DeviceController(MillenniaDevice(portPath="/dev/cu.usbmodem1"))

    def on_status(notification):
        print(notification.userInfo)   # {'power': .., 'isLaserOn': .., ...}

    NotificationCenter().addObserver(self, on_status, N.status)
    controller.start()
    controller.connect()
    controller.submit(lambda device: device.turnOn())
    ...
    controller.stop()
"""

import queue
import time
from enum import Enum
from threading import Event, RLock, Thread

from hardwarelibrary.notificationcenter import NotificationCenter

__all__ = [
    "DeviceController",
    "DeviceControllerNotification",
    "connection_error_reason",
]


class DeviceControllerNotification(Enum):
    """Notifications posted by a DeviceController (the controller is the object).

    userInfo payloads:
      didConnect       -> the device
      didDisconnect    -> None
      connectionLost   -> the exception that revealed the drop
      connectionFailed -> the exception from the failed (re)connect attempt
      status           -> the dict from device.doGetStatusUserInfo()
      commandFailed    -> the exception raised by the submitted command
    """
    didConnect = "didConnect"
    didDisconnect = "didDisconnect"
    connectionLost = "connectionLost"
    connectionFailed = "connectionFailed"
    status = "status"
    commandFailed = "commandFailed"


def connection_error_reason(error):
    """Classify a connection exception as 'busy'/'permission'/'missing'/None.

    Walks the exception's __cause__/__context__ chain (PhysicalDevice drivers
    are encouraged to preserve the underlying transport error) and matches it
    against common serial-port failure strings. Toolkit-agnostic and free of
    any pyserial import, so a front-end can turn a connectionFailed/lost
    notification into a human message without re-probing the port.
    """
    parts, seen, current = [], set(), error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = str(current).strip()
        if text:
            parts.append(text)
        current = current.__cause__ or current.__context__
    text = " | ".join(parts).lower()
    if "resource busy" in text or "errno 16" in text or "busy" in text:
        return "busy"
    if "permission" in text or "errno 13" in text or "access is denied" in text:
        return "permission"
    if ("no such file" in text or "errno 2" in text or "could not open" in text
            or "filenotfounderror" in text):
        return "missing"
    return None


class DeviceController:
    """Drive a PhysicalDevice from a single worker thread, reporting via notifications.

    Args:
        device: any PhysicalDevice instance.
        poll_interval: seconds between status polls while connected. The poll
            calls device.doGetStatusUserInfo(); if the device has none (returns
            None), polling is disabled automatically.
        reconnect_interval: seconds between reconnection attempts while
            disconnected-but-wanted.
        auto_reconnect: when True, an unexpected drop (or a connect that fails
            because the device is not yet present) is retried until it succeeds
            or disconnect() is called. When False, a single failure gives up.
    """

    def __init__(self, device, poll_interval=1.0, reconnect_interval=2.0,
                 auto_reconnect=True):
        self.device = device
        self.poll_interval = poll_interval
        self.reconnect_interval = reconnect_interval
        self.auto_reconnect = auto_reconnect

        self._queue = queue.Queue()
        self._stop = Event()
        self._lock = RLock()
        self._thread = Thread(target=self._run, name="DeviceController",
                              daemon=True)

        self._connected = False
        self._want_connected = False
        self._supports_status = True   # set False if doGetStatusUserInfo()->None
        self._next_poll = 0.0
        self._next_reconnect = 0.0
        self._last_failure_signature = None

    # -- public API (any thread) --

    def start(self):
        """Start the worker thread."""
        self._thread.start()

    def connect(self):
        """Request connection (and, with auto_reconnect, keep it connected)."""
        self._queue.put(("connect", None))

    def disconnect(self):
        """Request disconnection; clears the reconnect intent."""
        self._queue.put(("disconnect", None))

    def submit(self, action, name=None):
        """Run ``action(device)`` on the worker thread.

        Returns immediately. On failure a commandFailed notification is posted
        with the exception. A status poll is forced right after a successful
        command so observers see the new state promptly.
        """
        self._queue.put(("command", (action, name)))

    def stop(self):
        """Stop the worker thread and shut the device down."""
        self._stop.set()
        self._queue.put(("disconnect", None))
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)

    @property
    def is_connected(self):
        with self._lock:
            return self._connected

    @property
    def is_running(self):
        return self._thread.is_alive()

    # -- worker thread --

    def _post(self, name, userInfo=None):
        NotificationCenter().postNotification(name, notifyingObject=self,
                                              userInfo=userInfo)

    def _run(self):
        while not self._stop.is_set():
            try:
                task = self._queue.get(timeout=self._seconds_until_due())
            except queue.Empty:
                task = None

            if task is not None:
                self._handle(task)

            now = time.monotonic()
            if self._connected and self._supports_status and now >= self._next_poll:
                self._next_poll = now + self.poll_interval
                self._poll()
            elif (not self._connected and self._want_connected
                  and now >= self._next_reconnect):
                self._next_reconnect = now + self.reconnect_interval
                self._attempt_connect()

        self._teardown()

    def _seconds_until_due(self):
        now = time.monotonic()
        if self._connected:
            target = self._next_poll if self._supports_status else now + 0.5
        elif self._want_connected:
            target = self._next_reconnect
        else:
            return None  # nothing scheduled; block until a task arrives
        return max(0.0, target - now)

    def _handle(self, task):
        kind, payload = task
        if kind == "connect":
            self._want_connected = True
            self._next_reconnect = 0.0
            self._attempt_connect()
        elif kind == "disconnect":
            self._want_connected = False
            self._do_disconnect()
        elif kind == "command":
            self._do_command(*payload)

    def _attempt_connect(self):
        with self._lock:
            if self._connected:
                return
        try:
            self.device.initializeDevice()
        except Exception as error:
            self._connected = False
            self._post_failure_if_new(
                DeviceControllerNotification.connectionFailed, error)
            if not self.auto_reconnect:
                self._want_connected = False
            return

        with self._lock:
            self._connected = True
        self._supports_status = True
        self._next_poll = time.monotonic()  # poll immediately
        self._last_failure_signature = None
        self._post(DeviceControllerNotification.didConnect, userInfo=self.device)

    def _poll(self):
        try:
            info = self.device.doGetStatusUserInfo()
        except Exception as error:
            self._handle_lost(error)
            return
        if info is None:
            # Device exposes no status snapshot; stop polling for it.
            self._supports_status = False
            return
        self._post(DeviceControllerNotification.status, userInfo=info)

    def _do_command(self, action, name):
        if not self.is_connected:
            self._post(DeviceControllerNotification.commandFailed,
                       userInfo=RuntimeError(
                           "Cannot run command {0!r}: not connected".format(name)))
            return
        try:
            action(self.device)
        except Exception as error:
            # A failed command may mean the link dropped; verify with a poll.
            self._post(DeviceControllerNotification.commandFailed, userInfo=error)
            self._poll()
            return
        # Reflect the new state promptly.
        if self._supports_status:
            self._next_poll = time.monotonic()
            self._poll()

    def _handle_lost(self, error):
        was_connected = self._connected
        with self._lock:
            self._connected = False
        self._safe_shutdown()
        self._next_reconnect = time.monotonic() + self.reconnect_interval
        if not self.auto_reconnect:
            self._want_connected = False
        if was_connected:
            self._post(DeviceControllerNotification.connectionLost, userInfo=error)

    def _do_disconnect(self):
        with self._lock:
            self._connected = False
        self._safe_shutdown()
        self._post(DeviceControllerNotification.didDisconnect)

    def _safe_shutdown(self):
        try:
            self.device.shutdownDevice()
        except Exception:
            pass

    def _post_failure_if_new(self, name, error):
        # Avoid flooding identical connectionFailed notifications every interval
        # while a device stays unavailable; re-post only when the reason changes.
        signature = (type(error).__name__, connection_error_reason(error) or str(error))
        if signature != self._last_failure_signature:
            self._last_failure_signature = signature
            self._post(name, userInfo=error)

    def _teardown(self):
        if self._connected:
            with self._lock:
                self._connected = False
            self._safe_shutdown()
