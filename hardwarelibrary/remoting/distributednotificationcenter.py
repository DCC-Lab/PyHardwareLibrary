"""DistributedNotificationCenter: a Pyro5-based, cross-process NotificationCenter.

A single central broker (a Pyro object) holds the observers; posters call post()
and the broker fans out to matching observers via oneway callbacks. Each process
uses a `DistributedNotificationCenter` singleton that mirrors NotificationCenter's
API (addObserver / removeObserver / postNotification) but over the wire, so an
observer in one process receives notifications posted in another -- and a handler
gets the same Notification(name, object, userInfo) shape it would locally.

The broker is located via the HWLIB_DNC_URI environment variable. For the
same-machine prototype, the launcher starts one with ensureBroker() and exports
its URI so spawned device hosts inherit it; cross-machine, it would be registered
in the Pyro name server instead.

Requires the optional `Pyro5` dependency.
"""
import os
import threading
from enum import Enum

import Pyro5.api
import Pyro5.errors

from hardwarelibrary.notificationcenter import Notification
from hardwarelibrary.remotable import resolveNotificationName, _coercePayload


def _nameOf(notificationName):
    return notificationName.name if isinstance(notificationName, Enum) else notificationName


def _idFor(obj):
    """Stable cross-process id for a notifying/observed object.

    A ProxyDevice carries `_deviceId` (its Pyro URI); a real device on a host is
    tagged with `_distributedNotificationId` when bridged. Both ends use the same
    URI for the same device, so observer and poster match.
    """
    if obj is None:
        return None
    deviceId = getattr(obj, "_deviceId", None) or getattr(obj, "_distributedNotificationId", None)
    return deviceId if deviceId is not None else f"local:{id(obj)}"


@Pyro5.api.expose
class NotificationBroker:
    """Central registry + fan-out. Observers are keyed by (name, objectId)."""

    def __init__(self):
        self._observers = []  # (callbackUri, name, objectId)
        self._lock = threading.Lock()

    def register(self, callbackUri, name, objectId):
        with self._lock:
            entry = (callbackUri, name, objectId)
            if entry not in self._observers:
                self._observers.append(entry)

    def unregister(self, callbackUri, name=None, objectId=None):
        with self._lock:
            self._observers = [
                (uri, n, o) for (uri, n, o) in self._observers
                if not (uri == callbackUri
                        and (name is None or n == name)
                        and (objectId is None or o == objectId))]

    def post(self, name, notifyingObjectId, userInfo):
        with self._lock:
            targets = [uri for (uri, n, o) in self._observers
                       if n == name and (o is None or o == notifyingObjectId)]
        dead = []
        for uri in targets:
            try:
                # Create the callback proxy on this (delivering) thread; Pyro
                # proxies cannot be shared across the daemon's pool threads.
                proxy = Pyro5.api.Proxy(uri)
                proxy._pyroOneway.add("notify")
                proxy.notify(name, notifyingObjectId, userInfo)
            except Pyro5.errors.CommunicationError:
                dead.append(uri)
        if dead:
            with self._lock:
                self._observers = [(uri, n, o) for (uri, n, o) in self._observers if uri not in dead]


@Pyro5.api.expose
class ObserverCallback:
    def __init__(self, center):
        self._center = center

    @Pyro5.api.oneway
    def notify(self, name, notifyingObjectId, userInfo):
        self._center._deliver(name, notifyingObjectId, userInfo)


class DistributedNotificationCenter:
    """Per-process front end to the central broker. Singleton, like NotificationCenter."""

    _instance = None
    _classLock = threading.Lock()
    _brokerDaemon = None  # kept alive if this process hosts the broker

    def __new__(cls):
        with cls._classLock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._setUp()
            return cls._instance

    def _setUp(self):
        self._broker = None
        self._daemon = None
        self._callback = None
        self._callbackUri = None
        self._handlers = {}   # (name, objectId) -> [handler]
        self._objects = {}    # objectId -> the local object to report as notification.object
        self._lock = threading.Lock()

    # -- broker discovery / hosting -----------------------------------------
    @classmethod
    def ensureBroker(cls):
        """Start a central broker in this process if one is not already known,
        and export its URI (HWLIB_DNC_URI) so child processes share it."""
        uri = os.environ.get("HWLIB_DNC_URI")
        if uri:
            return uri
        daemon = Pyro5.api.Daemon(host="127.0.0.1")
        uri = str(daemon.register(NotificationBroker()))
        threading.Thread(target=daemon.requestLoop, name="DNC-broker", daemon=True).start()
        cls._brokerDaemon = daemon
        os.environ["HWLIB_DNC_URI"] = uri
        return uri

    def _brokerProxy(self):
        if self._broker is None:
            uri = os.environ.get("HWLIB_DNC_URI")
            if not uri:
                raise RuntimeError(
                    "No DistributedNotificationCenter broker; set HWLIB_DNC_URI or call ensureBroker()")
            self._broker = Pyro5.api.Proxy(uri)
        return self._broker

    def _ensureCallbackDaemon(self):
        if self._daemon is None:
            self._callback = ObserverCallback(self)
            self._daemon = Pyro5.api.Daemon(host="127.0.0.1")
            self._callbackUri = str(self._daemon.register(self._callback))
            threading.Thread(target=self._daemon.requestLoop, name="DNC-callback", daemon=True).start()

    # -- NotificationCenter-shaped API --------------------------------------
    def addObserver(self, handler, notificationName, observedObject=None):
        name = _nameOf(notificationName)
        objectId = _idFor(observedObject)
        self._ensureCallbackDaemon()
        with self._lock:
            self._handlers.setdefault((name, objectId), []).append(handler)
            if observedObject is not None:
                self._objects[objectId] = observedObject
        self._brokerProxy().register(self._callbackUri, name, objectId)

    def removeObserver(self, handler, notificationName=None, observedObject=None):
        name = _nameOf(notificationName) if notificationName is not None else None
        objectId = _idFor(observedObject) if observedObject is not None else None
        with self._lock:
            for key in list(self._handlers):
                keyName, keyObjectId = key
                if (name is None or keyName == name) and (objectId is None or keyObjectId == objectId):
                    self._handlers[key] = [h for h in self._handlers[key] if h is not handler]
                    if not self._handlers[key]:
                        del self._handlers[key]
        try:
            self._brokerProxy().unregister(self._callbackUri, name, objectId)
        except Exception:
            pass

    def postNotification(self, notificationName, notifyingObject=None, userInfo=None):
        self._brokerProxy().post(
            _nameOf(notificationName), _idFor(notifyingObject), _coercePayload(userInfo))

    def _deliver(self, name, notifyingObjectId, userInfo):
        with self._lock:
            handlers = list(self._handlers.get((name, notifyingObjectId), []))
            handlers += list(self._handlers.get((name, None), []))
            obj = self._objects.get(notifyingObjectId, notifyingObjectId)
        try:
            member = resolveNotificationName(name)
        except ValueError:
            return
        notification = Notification(member, obj, userInfo)
        for handler in handlers:
            try:
                handler(notification)
            except Exception:
                pass


def bridgeDeviceToBroker(device, deviceId):
    """In a device-host process: republish every notification this device posts to
    the central broker, tagged with deviceId, so remote observers receive it.
    Drivers are unchanged -- they keep posting to the in-process NotificationCenter.
    """
    from hardwarelibrary.notificationcenter import NotificationCenter
    from hardwarelibrary.remotable import _allNotificationMembers

    device._distributedNotificationId = deviceId
    center = DistributedNotificationCenter()

    def forward(notification):
        center.postNotification(
            notification.name, notifyingObject=device, userInfo=notification.userInfo)

    for member in _allNotificationMembers():
        NotificationCenter().addObserver(
            observer=("dnc-bridge", deviceId), method=forward,
            notificationName=member, observedObject=device)
