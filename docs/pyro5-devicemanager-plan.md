# Remote Device Access over Pyro5 — Design Notes

> Status: **planned, not started.** Design decisions reviewed and updated
> 2026-06-15. This document captures the design and the Pyro5 research so we can
> pick it up without re-deriving everything.

## Motivation

The current `DeviceManager` (`hardwarelibrary/devicemanager.py`) is an in-process
singleton: it monitors USB, instantiates driver objects, holds them in a `set`,
talks to them with direct method calls, and broadcasts state through an
in-process `NotificationCenter`. That works well **on the machine the hardware is
attached to**, and there is nothing wrong with it for local use.

What is missing is **cross-machine control**: running an app on one machine that
drives a device physically attached to another (e.g. a stage on a lab host). USB
monitoring and a device's live object (it owns a port, an `RLock`, a monitoring
`Thread`) are inherently local and single-owner — so the device must stay owned
by a per-host server where the hardware lives, and a remote app reaches it through
a handle.

## Goal

Let a Python app on machine A drive a device attached to machine B as if it were
local, and receive that device's events. Each machine with hardware runs a
**device server** that discovers its local devices and advertises each one in a
**Pyro5 name server assumed to be running somewhere on the LAN**. A client looks a
device up and gets a **proxy it drives as if the device were local**. Device
events reach remote clients via **Pyro5 callbacks**.

## Approach: additive transport, not a rewrite

Remote access is a **new transport layered on top of the existing local API**, not
a replacement for it:

- The in-process `DeviceManager` and the direct-drive path **stay**. An app on the
  same box as the hardware keeps driving the device directly, with no Pyro hop.
- A remote app obtains a **`RemoteDevice` proxy that presents the same public
  interface** as the device (`moveTo`, `moveBy`, `position`, `home`, …), so
  **application code is identical** whether the handle is a local `PhysicalDevice`
  or a remote proxy. Only how you obtain the handle differs: `DeviceManager`
  locally vs `RemoteDeviceManager` remotely.
- Driver files and the device/family classes are **unchanged**.

This keeps the local path fast, de-risks the change (we add a layer instead of
ripping out a working one), and means the remote API can be adopted incrementally.

### Locked-in decisions

- **Python-only clients** — so Pyro5 (Python-native remote objects) is an
  acceptable, ergonomic transport.
- **Cross-machine control** is the requirement that justifies a remoting layer.
- **Name server assumed running somewhere on the LAN.** Servers and clients locate
  it by **broadcast** (`Pyro5.api.locate_ns()` with no host), with a
  **`PYRO_NS_HOST` env-var override** for when it must be pinned (e.g. across
  subnets, where broadcast is dropped). Not hardcoded to a specific host.
- **Additive** — keep the in-process `DeviceManager` and the local API
  (`anyLinearMotionDevice()`, `matchPhysicalDevicesOfType()`,
  `DeviceManagerNotification`, …). Remote access is a new, parallel transport.
- The **client proxy presents the same interface as the device**, so app code is
  transport-agnostic.
- Events pushed to remote clients via Pyro5 **oneway callbacks**.
- Device discovery via the Pyro5 name server (metadata lookup).
- **Pyro5 is an optional extra** (`pip install hardwarelibrary[remote]`), not a
  core dependency — only the server host and remote clients need it.
- **Scale assumption: one or two known hardware hosts.** The name server is for
  *location transparency* (the app asks for "the stage" without knowing which box
  it is on), not for managing a fleet.
- **The name server has no liveness checking.** A device can be listed while its
  server is dead, so the client treats a looked-up proxy that will not connect as
  *gone*, and servers unregister their devices on clean shutdown.

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
- **Name server discovery**: `Pyro5.api.locate_ns()` with no host broadcasts on
  the LAN and finds the NS wherever it runs; `locate_ns(host=...)` (or
  `PYRO_NS_HOST`) pins it. `pyro5-ns` runs the broadcast responder by default.
  Registration/lookup: `ns.register(name, uri, metadata={...})`,
  `ns.yplookup(meta_all={...})`, `ns.list(prefix=..., return_metadata=True)`.
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

### `hardwarelibrary/devicemonitor.py` — shared USB monitoring
Factor `USBDeviceDescriptor` and the connect/disconnect diff
(`newlyConnectedAndDisconnectedUSBDevices`) into a standalone module that **both**
the existing in-process `DeviceManager` **and** the new `DeviceServer` import — one
discovery implementation, no duplication, nothing deleted. Reuses
`utils.connectedUSBDevices`, `utils.getAllUSBIds`, `utils.getCandidateDeviceClasses`
(`hardwarelibrary/utils.py`) — no new discovery logic.

### `hardwarelibrary/server/deviceserver.py` — `DeviceServer`
- `__init__(nameServerHost=None, hostname=None)` — `nameServerHost=None` means
  locate the NS by broadcast (honoring `PYRO_NS_HOST` if set); `hostname` defaults
  to `socket.gethostname()`.
- `start()`: create threaded `Pyro5.api.Daemon(host=reachableHost)`, `locate_ns()`
  (broadcast or pinned), discover local devices, instantiate each driver,
  `uri = daemon.register(servant)`,
  `ns.register(nameFor(servant), uri, metadata=metadataFor(servant))`, track
  `{serialNumber: (servant, uri, nsName)}`, start a hot-plug poll thread, then
  `daemon.requestLoop()`.
- Hot-plug: on connect register servant + NS name; on disconnect `ns.remove(...)`,
  `daemon.unregister(...)`, shut the device down.
- `nameFor()` -> `hardware.<hostname>.<family>.<serialNumber>`.
- `metadataFor()` -> `{"hardware", "family:<f>", "type:<t>", "host:<h>", "serial:<s>"}`.
- `stop()` / SIGINT: unregister all (so the NS does not keep stale entries), shut
  down devices, `daemon.shutdown()`.

### `hardwarelibrary/server/__main__.py`
`python -m hardwarelibrary.server [--nameserver HOST] [--hostname HOST]`
(`--nameserver` optional; default is broadcast discovery).

### `hardwarelibrary/client/deviceproxy.py` — `RemoteDevice`
Wraps a `Pyro5.api.Proxy` and **presents the same public interface as the device**
so callers cannot tell local from remote. `__getattr__` turns `device.moveTo(...)`
into `proxy.callMethod("moveTo", ...)`; properties (`state`, `serialNumber`) call
`getProperty`/`stateValue` and coerce types back (int -> `DeviceState`, list ->
`tuple` for `position()`). `subscribe(notificationName, handler)` /
`unsubscribe(...)`. A proxy that will not connect is reported as *gone* (the NS may
list a device whose server has died). Surfaces `Pyro5.errors.get_pyro_traceback()`
on errors.

### `hardwarelibrary/client/notificationcallback.py` — `NotificationCallback`
`@Pyro5.api.expose` class with `@Pyro5.api.callback @Pyro5.api.oneway notify(self,
payload: dict)` that rebuilds typed values and dispatches to registered handlers.

### `hardwarelibrary/client/remotedevicemanager.py` — `RemoteDeviceManager`
Presents a lookup API **compatible with the local `DeviceManager`**, so swapping
local for remote is mechanical.
- `__init__(nameServerHost=None)` — broadcast discovery by default; lazy `locate_ns`.
- `availableDevices() -> list[dict]` via `ns.list(prefix="hardware.", return_metadata=True)`.
- `devicesOfFamily(family) -> list[RemoteDevice]` via `ns.yplookup(meta_all={f"family:{family}"})`.
- `anyDeviceOfFamily(family)`, `deviceWithSerialNumber(serialNumber)`.
- Convenience wrappers mirroring the local API: `linearMotionDevices()`,
  `anyLinearMotionDevice()`, `spectrometerDevices()`, `powerMeterDevices()`
  (classify via NS metadata / servant `family()`, since `isinstance` is impossible
  across a proxy).
- Lazily starts a background `Pyro5.api.Daemon` thread and one shared
  `NotificationCallback` used for all subscriptions.

### `hardwarelibrary/tests/testPyroDeviceManager.py`
In-process name server + daemon (no hardware, no network). Uses the existing
`DebugLinearMotionDevice`. Tests: register a debug device and find it via
`yplookup`; get a proxy and drive `initializeDevice`/`moveTo`/`position`;
`DeviceState` round-trips as an IntEnum; forced init error propagates as
`PhysicalDevice.UnableToInitialize`; subscribe to `didMove`, drive `moveTo`, and
assert the callback handler receives a payload with `name == "didMove"`. Any test
needing real hardware, a real network, or a broadcast NS calls `self.skipTest(...)`.

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

- `pyproject.toml` — add an optional extra `remote = ["Pyro5"]` (matching the
  existing `dev` / `docs` / `thorlabs` extras), and a `[project.scripts]` server
  entry. Pyro5 stays out of the core dependencies.
- `hardwarelibrary/__init__.py` — **keep** `from .devicemanager import *`;
  **additionally** export `RemoteDeviceManager` and the server package.
- `hardwarelibrary/__main__.py` — **keep** the existing local `-dm` branch; **add**
  `--serve` (run `DeviceServer`) and a remote lookup mode
  (`RemoteDeviceManager` lists/subscribes via the broadcast NS).
- `hardwarelibrary/devicemanager.py` — **kept.** Move the reusable monitoring
  pieces (`USBDeviceDescriptor`, connect/disconnect diff) into
  `devicemonitor.py` and have `DeviceManager` import them, so the local manager and
  the server share one implementation. The singleton DM API is unchanged.
- `hardwarelibrary/tests/testDeviceManager.py` — **kept** (local path still works);
  `testPyroDeviceManager.py` is added alongside it.
- `physicaldevice.py` and family bases — **no changes** (the servant handles
  exposure; this is the payoff of the dispatcher design).

## Deployment

- Name server: run it **somewhere** on the LAN (e.g. a `systemd` service on one
  lab box) with `pyro5-ns` — the broadcast responder is on by default. It need not
  be on any particular host.
- Each hardware host: `python -m hardwarelibrary.server` (add `--nameserver HOST`
  or set `PYRO_NS_HOST` only if broadcast cannot reach the NS).
- Clients: `RemoteDeviceManager()` (broadcast) or `RemoteDeviceManager("host")`.
- Document the network-reachable-host binding gotcha (daemon must bind a routable
  host, not localhost).

## Implementation order

1. `pyproject.toml` `remote` extra; `pip install -e ".[remote]"` into `.venv`.
2. `serialization.py` + round-trip unit checks.
3. `devicemonitor.py` (extract shared monitoring; `DeviceManager` keeps working).
4. `server/deviceservant.py` (dispatcher, `FAMILY_METHODS`, lifecycle, subscribe).
5. `client/deviceproxy.py` + `client/notificationcallback.py`.
6. `server/deviceserver.py` + `server/__main__.py`.
7. `client/remotedevicemanager.py`.
8. `tests/testPyroDeviceManager.py` (in-process NS + daemon).
9. Wire `__init__.py` / `__main__.py` additively (local `-dm` stays; add `--serve`
   and remote lookup). No deletions.

## Verification

- `.venv/bin/python -m pytest hardwarelibrary/tests/testPyroDeviceManager.py -v`
  (in-process NS + daemon; debug device; covers proxy drive, state serialization,
  exception propagation, and a callback round-trip).
- Confirm the local path is untouched:
  `.venv/bin/python -m pytest hardwarelibrary/tests/testDeviceManager.py hardwarelibrary/tests/testPhysicalDevice.py -v`.
- Manual cross-machine smoke test (needs a running NS): start `pyro5-ns` somewhere,
  then `python -m hardwarelibrary.server` on a hardware host, then on another
  machine `RemoteDeviceManager().availableDevices()` and drive a returned
  `RemoteDevice`.

## Open questions to revisit

- Authentication / access control on the lab network (Pyro5 HMAC key, serializer
  trust). Currently assumed trusted network.
- Whether the per-device background status thread should run on the server and
  forward via callbacks, or be driven on demand by client polling.
- Whether to add active liveness checking (the client currently treats an
  unreachable proxy as gone; a periodic NS sweep that prunes dead servers is an
  option if stale entries become a nuisance).
