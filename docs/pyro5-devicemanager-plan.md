# Pyro5-Native DeviceManager Rewrite — Design Notes

> Status: **planned, not started.** Parked for later discussion (deliberately a
> big change). This document captures the design and the Pyro5 research so we can
> pick it up without re-deriving everything.

## Motivation

The current `DeviceManager` (`hardwarelibrary/devicemanager.py`) is an in-process
singleton: it monitors USB, instantiates driver objects, holds them in a `set`,
talks to them with direct method calls, and broadcasts state through an
in-process `NotificationCenter`. The hand-rolled wiring between the manager and
the device objects is clunky and buggy, and only works within one Python process
on one machine.

## Goal

Cross-machine control. A Pyro5 **name server runs on host `cafeine3`**. Any
machine with hardware attached runs a **device server** that discovers its local
devices and advertises each one in the name server. A client anywhere looks a
device up and gets a **proxy it drives as if the device were local**. Device
events reach remote clients via **Pyro5 callbacks**.

This is a clean rewrite: new Pyro5-native API, existing callers rewritten, old
singleton API removed.

### Locked-in decisions

- Cross-machine, name server on `cafeine3`.
- Events pushed to remote clients via Pyro5 callbacks.
- Clean rewrite — do not preserve the old singleton / `anyLinearMotionDevice()` /
  `matchPhysicalDevicesOfType()` / `DeviceManagerNotification` API.
- Device discovery via the Pyro5 name server.

## Key Pyro5 facts driving the design (verified against pyro5.readthedocs.io)

- **`@expose` does not reliably propagate to subclass-defined methods.** Drivers
  add their own public methods on top of the family base. Rather than decorate
  `PhysicalDevice` + every family base + every driver, wrap each device in a
  **servant** that exposes one generic dispatcher. Driver files stay untouched.
- Pyro **autoproxies** objects registered with a daemon and serializes everything
  else by value. Our devices hold `RLock`/`Thread`/`port` and are unpicklable, so
  we never return a device — only the registered servant.
- The default **serpent** serializer can't move arbitrary objects; coerce custom
  return types (`DeviceState`, position tuples, errors) to primitives at the
  boundary. serpent also turns tuples into lists — coerce back client-side.
- **Callbacks**: the client runs its own daemon thread, registers a callback
  object, and passes its proxy to the server. Callback `notify` is `@oneway` so a
  slow/dead client can never block the device server.
- Name server API: `Pyro5.api.locate_ns(host="cafeine3")`;
  `ns.register(name, uri, metadata={...})`; `ns.yplookup(meta_all={...})`;
  `ns.list(prefix=..., return_metadata=True)`.
- A hardware-host daemon must bind a **network-reachable host** (not `localhost`)
  or the URIs it hands out are unreachable from other machines.

## New files

### `hardwarelibrary/serialization.py`
`registerSerializers()` (idempotent) registers serpent hooks for the few custom
types that may cross the wire (e.g. `PhysicalDevice.UnableToInitialize` /
`UnableToShutdown` / `ClassIncompatibleWithRequestedDevice` / `NotInitialized` so
they re-raise as the right type client-side). The common path avoids registration
by coercing at the API boundary (state as `int`, positions as lists).

### `hardwarelibrary/server/deviceservant.py` — `DeviceServant`
Wraps one `PhysicalDevice`; this is the object registered with the daemon.
`@Pyro5.api.expose` + `@Pyro5.api.behavior(instance_mode="single")`. Exposed surface:
- `callMethod(self, methodName, *args, **kwargs)` — validates `methodName` against
  a per-family whitelist (`FAMILY_METHODS`, keyed by family base class, e.g.
  `LinearMotionDevice -> {moveTo, moveBy, position, home, ...}`), then
  `getattr(self.device, methodName)(*args, **kwargs)`. One exposed method covers
  the whole rich API and the whitelist blocks arbitrary remote attribute calls.
- `getProperty(name)` / `setProperty(name, value)` for attributes.
- `deviceType() -> str`, `family() -> str`, `serialNumber() -> str`,
  `idVendor() -> int`, `idProduct() -> int`, `stateValue() -> int`.
- lifecycle wrappers: `initializeDevice`, `shutdownDevice`,
  `startBackgroundStatusUpdates`, `stopBackgroundStatusUpdates`.
- event bridge: `subscribe(callbackProxy, notificationName)` /
  `unsubscribe(callbackProxy, notificationName=None)`.

### `hardwarelibrary/server/usbmonitor.py`
Port `USBDeviceDescriptor` and the connect/disconnect diff
(`newlyConnectedAndDisconnectedUSBDevices`) out of the old `devicemanager.py`.
Reuses `utils.connectedUSBDevices`, `utils.getAllUSBIds`,
`utils.getCandidateDeviceClasses` (`hardwarelibrary/utils.py`) — no new discovery logic.

### `hardwarelibrary/server/deviceserver.py` — `DeviceServer`
- `__init__(nameServerHost="cafeine3", hostname=None)` (`hostname` defaults to
  `socket.gethostname()`).
- `start()`: create threaded `Pyro5.api.Daemon(host=reachableHost)`,
  `locate_ns(host=nameServerHost)`, discover local devices, instantiate each
  driver, `uri = daemon.register(servant)`,
  `ns.register(nameFor(servant), uri, metadata=metadataFor(servant))`, track
  `{serialNumber: (servant, uri, nsName)}`, start a hot-plug poll thread, then
  `daemon.requestLoop()`.
- Hot-plug: on connect register servant + NS name; on disconnect `ns.remove(...)`,
  `daemon.unregister(...)`, shut the device down.
- `nameFor()` -> `hardware.<hostname>.<family>.<serialNumber>`.
- `metadataFor()` -> `{"hardware", "family:<f>", "type:<t>", "host:<h>", "serial:<s>"}`.
- `stop()` / SIGINT: unregister all, shut down devices, `daemon.shutdown()`.

### `hardwarelibrary/server/__main__.py`
`python -m hardwarelibrary.server [--nameserver cafeine3] [--hostname HOST]`.

### `hardwarelibrary/client/deviceproxy.py` — `RemoteDevice`
Wraps a `Pyro5.api.Proxy`. `__getattr__` turns `device.moveTo(...)` into
`proxy.callMethod("moveTo", ...)`; properties (`state`, `serialNumber`) call
`getProperty`/`stateValue` and coerce types back (int -> `DeviceState`, list ->
`tuple` for `position()`). `subscribe(notificationName, handler)` /
`unsubscribe(...)`. Surfaces `Pyro5.errors.get_pyro_traceback()` on errors.

### `hardwarelibrary/client/notificationcallback.py` — `NotificationCallback`
`@Pyro5.api.expose` class with `@Pyro5.api.callback @Pyro5.api.oneway notify(self,
payload: dict)` that rebuilds typed values and dispatches to registered handlers.

### `hardwarelibrary/client/remotedevicemanager.py` — `RemoteDeviceManager`
- `__init__(nameServerHost="cafeine3")`; lazy `locate_ns`.
- `availableDevices() -> list[dict]` via `ns.list(prefix="hardware.", return_metadata=True)`.
- `devicesOfFamily(family) -> list[RemoteDevice]` via `ns.yplookup(meta_all={f"family:{family}"})`.
- `anyDeviceOfFamily(family)`, `deviceWithSerialNumber(serialNumber)`.
- Convenience wrappers: `linearMotionDevices()`, `anyLinearMotionDevice()`,
  `spectrometerDevices()`, `powerMeterDevices()` (classify via NS metadata /
  servant `family()`, since `isinstance` is impossible across a proxy).
- Lazily starts a background `Pyro5.api.Daemon` thread and one shared
  `NotificationCallback` used for all subscriptions.

### `hardwarelibrary/tests/testPyroDeviceManager.py`
In-process name server + daemon (no hardware, no network). Uses the existing
`DebugLinearMotionDevice`. Tests: register a debug device and find it via
`yplookup`; get a proxy and drive `initializeDevice`/`moveTo`/`position`;
`DeviceState` round-trips as an IntEnum; forced init error propagates as
`PhysicalDevice.UnableToInitialize`; subscribe to `didMove`, drive `moveTo`, and
assert the callback handler receives a payload with `name == "didMove"`. Any test
needing real hardware or the real `cafeine3` NS calls `self.skipTest(...)`.

## Event bridge

The device keeps posting to the in-process `NotificationCenter` exactly as today
(**no driver changes**). On first `subscribe(name)`, the servant adds a
`NotificationCenter` observer scoped to its device. `forwardNotification` builds a
**primitives-only** payload — `{"name": notification.name.value, "deviceName":
nsName, "deviceSerialNumber": serial, "userInfo": <coerced primitives>}` — and
pushes it to each subscriber via the oneway callback. Pyro communication errors
mark the subscriber dead and drop it; removing the last subscriber for a name
removes the observer.

## Existing files to modify

- `pyproject.toml` — add `Pyro5` to `[project].dependencies`; add a
  `[project.scripts]` server entry.
- `hardwarelibrary/__init__.py` — drop `from .devicemanager import *`; export
  `RemoteDeviceManager` and the server package.
- `hardwarelibrary/__main__.py` — replace the `-dm` branch (old singleton +
  SIGINT handler) with `--serve` (run `DeviceServer`) and a rewritten `-dm`
  (`RemoteDeviceManager` lists/subscribes against `cafeine3`).
- `hardwarelibrary/devicemanager.py` — remove the singleton DM API
  (`DeviceManagerNotification`, per-family queries, `matchPhysicalDevicesOfType`,
  monitoring loop). Useful pieces (`USBDeviceDescriptor`, connect/disconnect diff)
  move to `server/usbmonitor.py`. File is then deleted.
- `hardwarelibrary/tests/testDeviceManager.py` — removed/replaced by
  `testPyroDeviceManager.py`. `testPhysicalDevice.py` keeps device-lifecycle
  tests, loses any DM-coupled cases.
- `physicaldevice.py` and family bases — **no changes** (the servant handles
  exposure; this is the payoff of the dispatcher design).

## Deployment

- Name server on cafeine3: `pyro5-ns -n cafeine3`.
- Each hardware host: `python -m hardwarelibrary.server --nameserver cafeine3`.
- Clients: `RemoteDeviceManager(nameServerHost="cafeine3")`.
- Document the network-reachable-host binding gotcha (daemon must bind a routable
  host, not localhost).

## Implementation order

1. `pyproject.toml` dep; `pip install` into `.venv`.
2. `serialization.py` + round-trip unit checks.
3. `server/deviceservant.py` (dispatcher, `FAMILY_METHODS`, lifecycle, subscribe).
4. `client/deviceproxy.py` + `client/notificationcallback.py`.
5. `server/usbmonitor.py` + `server/deviceserver.py` + `server/__main__.py`.
6. `client/remotedevicemanager.py`.
7. `tests/testPyroDeviceManager.py` (in-process NS + daemon).
8. Migrate `__main__.py`; prune tests; delete old `devicemanager.py`; update
   `__init__.py`.

## Verification

- `.venv/bin/python -m pytest hardwarelibrary/tests/testPyroDeviceManager.py -v`
  (in-process NS + daemon; debug device; covers proxy drive, state serialization,
  exception propagation, and a callback round-trip).
- Confirm existing suites still pass:
  `.venv/bin/python -m pytest hardwarelibrary/tests/testPhysicalDevice.py -v`.
- Manual cross-machine smoke test (needs the real NS): `pyro5-ns -n cafeine3`,
  then `python -m hardwarelibrary.server --nameserver cafeine3` on a hardware
  host, then on another machine
  `RemoteDeviceManager(nameServerHost="cafeine3").availableDevices()` and drive a
  returned `RemoteDevice`.

## Open questions to revisit

- Whether to keep the family-convenience wrappers (`anyLinearMotionDevice()` etc.)
  or go fully to `devicesOfFamily("linearMotion")`.
- Authentication / access control on the lab network (Pyro5 HMAC key, serializer
  trust). Currently assumed trusted network.
- Whether the per-device background status thread should run on the server and
  forward via callbacks, or be driven on demand by client polling.
