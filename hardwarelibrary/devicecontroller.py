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
    from notificationcenter import NotificationCenter
    from hardwarelibrary.sources.millennia import MillenniaDevice

    controller = DeviceController(MillenniaDevice(portPath="/dev/cu.usbmodem1"))

    def onStatus(notification):
        print(notification.user_info)   # {'power': .., 'isLaserOn': .., ...}

    NotificationCenter().add_observer(self, onStatus, N.status)
    controller.start()
    controller.connect()
    controller.submit(lambda device: device.turnOn())       # fire-and-forget
    reading = controller.submit(lambda device: device.power()).result()  # query
    ...
    controller.stop()
"""

import queue
import time
from concurrent.futures import Future
from enum import Enum
from threading import Event, RLock, Thread

from notificationcenter import NotificationCenter

__all__ = [
    "DeviceController",
    "DeviceControllerNotification",
    "connectionErrorReason",
]


class DeviceControllerNotification(Enum):
    """Notifications posted by a DeviceController (the controller is the object).

    user_info payloads:
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


def connectionErrorReason(error):
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
        pollInterval: seconds between status polls while connected. The poll
            calls device.doGetStatusUserInfo(); if the device has none (returns
            None), polling is disabled automatically.
        reconnectInterval: seconds between reconnection attempts while
            disconnected-but-wanted.
        autoReconnect: when True, an unexpected drop (or a connect that fails
            because the device is not yet present) is retried until it succeeds
            or disconnect() is called. When False, a single failure gives up.
    """

    def __init__(self, device, pollInterval=1.0, reconnectInterval=2.0,
                 autoReconnect=True):
        self.device = device
        self.pollInterval = pollInterval
        self.reconnectInterval = reconnectInterval
        self.autoReconnect = autoReconnect

        self.commandQueue = queue.Queue()
        self.stopEvent = Event()
        self.lock = RLock()
        self.thread = Thread(target=self.runLoop, name="DeviceController",
                             daemon=True)

        self.connected = False
        self.wantConnected = False
        self.supportsStatus = True   # set False if doGetStatusUserInfo()->None
        self.nextPoll = 0.0
        self.nextReconnect = 0.0
        self.lastFailureSignature = None

    # -- public API (any thread) --

    def start(self):
        """Start the worker thread."""
        self.thread.start()

    def connect(self):
        """Request connection (and, with autoReconnect, keep it connected)."""
        self.commandQueue.put(("connect", None))

    def disconnect(self):
        """Request disconnection; clears the reconnect intent."""
        self.commandQueue.put(("disconnect", None))

    def submit(self, action, name=None):
        """Run ``action(device)`` on the worker thread; return a Future.

        The Future resolves with the action's return value (so query-style
        devices can read a measurement back: ``controller.submit(lambda d:
        d.power()).result()``) or with its exception. On failure a commandFailed
        notification is also posted, for observers that don't hold the Future.
        A status poll is forced after a successful command so observers see the
        new state promptly. Do not block on ``.result()`` from a UI thread.
        """
        future = Future()
        self.commandQueue.put(("command", (action, name, future)))
        return future

    def stop(self):
        """Stop the worker thread and shut the device down."""
        self.stopEvent.set()
        self.commandQueue.put(("disconnect", None))
        if self.thread.is_alive():
            self.thread.join(timeout=5.0)

    @property
    def isConnected(self):
        with self.lock:
            return self.connected

    @property
    def isRunning(self):
        return self.thread.is_alive()

    # -- worker thread --

    def post(self, name, user_info=None):
        NotificationCenter().post_notification(name, notifying_object=self,
                                              user_info=user_info)

    def runLoop(self):
        while not self.stopEvent.is_set():
            try:
                task = self.commandQueue.get(timeout=self.secondsUntilDue())
            except queue.Empty:
                task = None

            if task is not None:
                self.handleTask(task)

            now = time.monotonic()
            if self.connected and self.supportsStatus and now >= self.nextPoll:
                self.nextPoll = now + self.pollInterval
                self.poll()
            elif (not self.connected and self.wantConnected
                  and now >= self.nextReconnect):
                self.nextReconnect = now + self.reconnectInterval
                self.attemptConnect()

        self.teardown()

    def secondsUntilDue(self):
        now = time.monotonic()
        if self.connected:
            target = self.nextPoll if self.supportsStatus else now + 0.5
        elif self.wantConnected:
            target = self.nextReconnect
        else:
            return None  # nothing scheduled; block until a task arrives
        return max(0.0, target - now)

    def handleTask(self, task):
        kind, payload = task
        if kind == "connect":
            self.wantConnected = True
            self.nextReconnect = 0.0
            self.attemptConnect()
        elif kind == "disconnect":
            self.wantConnected = False
            self.doDisconnect()
        elif kind == "command":
            self.doCommand(*payload)

    def attemptConnect(self):
        with self.lock:
            if self.connected:
                return
        try:
            self.device.initializeDevice()
        except Exception as error:
            self.connected = False
            self.postFailureIfNew(
                DeviceControllerNotification.connectionFailed, error)
            if not self.autoReconnect:
                self.wantConnected = False
            return

        with self.lock:
            self.connected = True
        self.supportsStatus = True
        self.nextPoll = time.monotonic()  # poll immediately
        self.lastFailureSignature = None
        self.post(DeviceControllerNotification.didConnect, user_info=self.device)

    def poll(self):
        try:
            info = self.device.doGetStatusUserInfo()
        except Exception as error:
            self.handleConnectionLost(error)
            return
        if info is None:
            # Device exposes no status snapshot; stop polling for it.
            self.supportsStatus = False
            return
        self.post(DeviceControllerNotification.status, user_info=info)

    def doCommand(self, action, name, future):
        if not future.set_running_or_notify_cancel():
            return  # the caller cancelled the Future before it ran
        if not self.isConnected:
            error = RuntimeError(
                "Cannot run command {0!r}: not connected".format(name))
            self.post(DeviceControllerNotification.commandFailed, user_info=error)
            future.set_exception(error)
            return
        try:
            result = action(self.device)
        except Exception as error:
            # A failed command may mean the link dropped; verify with a poll.
            self.post(DeviceControllerNotification.commandFailed, user_info=error)
            future.set_exception(error)
            self.poll()
            return
        future.set_result(result)
        # Reflect the new state promptly.
        if self.supportsStatus:
            self.nextPoll = time.monotonic()
            self.poll()

    def handleConnectionLost(self, error):
        wasConnected = self.connected
        with self.lock:
            self.connected = False
        self.safeShutdown()
        self.nextReconnect = time.monotonic() + self.reconnectInterval
        if not self.autoReconnect:
            self.wantConnected = False
        if wasConnected:
            self.post(DeviceControllerNotification.connectionLost, user_info=error)

    def doDisconnect(self):
        with self.lock:
            self.connected = False
        self.safeShutdown()
        self.post(DeviceControllerNotification.didDisconnect)

    def safeShutdown(self):
        try:
            self.device.shutdownDevice()
        except Exception:
            pass

    def postFailureIfNew(self, name, error):
        # Avoid flooding identical connectionFailed notifications every interval
        # while a device stays unavailable; re-post only when the reason changes.
        signature = (type(error).__name__, connectionErrorReason(error) or str(error))
        if signature != self.lastFailureSignature:
            self.lastFailureSignature = signature
            self.post(name, user_info=error)

    def teardown(self):
        if self.connected:
            with self.lock:
                self.connected = False
            self.safeShutdown()
