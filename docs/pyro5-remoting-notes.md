# Pyro5 Remoting — Implementation Notes (for review)

> Status: **prototype, same-machine, working.** Reviewed/updated 2026-06-17.
> Branch: `pyro5-devicemanager`. This documents what was actually built; the
> forward-looking design lives in `pyro5-devicemanager-plan.md`.

## What to review

Commits on the branch (newest first):

| Commit | What |
|---|---|
| `4678be3` | DistributedNotificationCenter; removed the forwarding/re-post bridge |
| `2edc7fb` | Promote `Remotable` onto `PhysicalDevice` (every device remotable) |
| `9038fe3` | Refactor to `Remotable` mixin + generic `ProxyDevice` |
| `6912bdb` | First prototype: process-isolated hosting over Pyro5 (localhost) |
| `adb797f` | Revise the plan doc (additive transport, broadcast NS) |
| `643cd16` | Original design notes |

Code (≈660 lines incl. tests):

- `hardwarelibrary/remotable.py` — `Remotable` mixin (core; Pyro-optional)
- `hardwarelibrary/remoting/distributednotificationcenter.py` — events
- `hardwarelibrary/remoting/deviceproxy.py` — `ProxyDevice` handle
- `hardwarelibrary/remoting/devicehost.py` — subprocess entry point
- `hardwarelibrary/remoting/isolation.py` — `createDevice` / `launchIsolatedDevice`
- `hardwarelibrary/remoting/__init__.py` — public exports
- `hardwarelibrary/tests/testIsolatedDevice.py` — 6 tests

## What it does

Lets you run a `PhysicalDevice` in **its own OS process** so a buggy third-party
driver crashes only that process, not your app — and drive it through a handle
that looks like the device. Same machine only for now; the Pyro5 machinery is the
same one cross-machine will use.

```python
from hardwarelibrary.remoting import createDevice, DistributedNotificationCenter
from hardwarelibrary.motion.linearmotiondevice import DebugLinearMotionDevice, LinearMotionNotification

stage = createDevice(DebugLinearMotionDevice, isolated=False)  # real device, in-process
stage = createDevice(DebugLinearMotionDevice, isolated=True)   # ProxyDevice, own process

stage.initializeDevice()
stage.moveTo((160, 320, 480))    # forwarded automatically
stage.position()                 # (160, 320, 480)
stage.state                      # DeviceState.Ready (read live)

# Observe a remote device with the same call shape as a local one:
DistributedNotificationCenter().addObserver(onMove, LinearMotionNotification.didMove, observedObject=stage)
```

## Architecture

Three pieces, all riding on Pyro5 over localhost:

1. **`Remotable` (on `PhysicalDevice`)** — every device can serve itself. Exposes
   two generic Pyro methods: `callMethod(name, *args)` and `getAttribute(name)`.
   One dispatcher forwards the whole API, so there is no per-method `@expose` and
   no servant wrapper. Pyro5 is optional: `expose` falls back to a no-op when
   Pyro5 is absent, so importing the library never requires it.

2. **`ProxyDevice`** — one generic, duck-typed client handle. `__getattr__`
   forwards any method to the remote via `callMethod`; the common
   `PhysicalDevice` attributes (`state`, `serialNumber`, …) are read live via
   `getAttribute`. It also **supervises the host process**: a dead host raises
   `IsolatedDeviceError` instead of hanging or crashing the caller. It is *not* an
   instance of the family ABC — driven by duck typing (see decisions below).

3. **`DistributedNotificationCenter`** — a Pyro-based, central pub/sub mirroring
   `NotificationCenter`'s API across processes. A central `NotificationBroker`
   (Pyro object) holds observers and fans out via oneway callbacks. A device host
   bridges its in-process `NotificationCenter` into the broker once at startup, so
   **drivers are unchanged**. Object identity crosses the wire as a stable id (the
   device's Pyro URI), so `observedObject=stage` filtering works and the handler
   receives the same `Notification(name, object, userInfo)`.

`createDevice(isolated=False)` returns the real device (in-process, `isinstance`
holds). `isolated=True` spawns a host process (`python -m
hardwarelibrary.remoting.devicehost`), which registers the device with a localhost
Pyro daemon and prints its URI; the parent wraps it in a `ProxyDevice`.

## Key design decisions (and rejected alternatives)

- **Additive, not a rewrite.** The in-process `DeviceManager` and local API stay;
  remoting is a new transport. Rejected the original plan's "delete the singleton
  API" clean rewrite.
- **`Remotable` mixin, device serves itself.** Rejected the separate
  `DeviceServant` wrapper. The generic `callMethod`/`getAttribute` dispatcher
  sidesteps Pyro5's "`@expose` does not inherit to subclass methods" gotcha.
- **One generic `ProxyDevice`, duck-typed.** It is *not* a per-device mirror and
  *not* an ABC subclass. Considered making the proxy an `isinstance`-true
  `LinearMotionDevice` (via a generated per-family proxy) — rejected because a
  "real device" handle carries live attributes (`state`, `x`, …) that can go stale
  vs the remote, requiring more interception machinery for little gain. Also
  considered a `typing.Protocol` — rejected: the project already removed Protocols
  (`CLAUDE.md`) to keep the ABC the single source of truth, and a Protocol would
  reintroduce a hand-maintained API mirror without removing any forwarding code.
- **Events via a central `DistributedNotificationCenter`.** Rejected an earlier
  approach that bolted per-device forwarding onto `Remotable` and **re-posted into
  the client's local `NotificationCenter`** via a callback registry — too spread
  out and it poked the core singleton. The DNC is one coherent component and
  generalizes to any notification/poster.
- **Pyro5 is an optional `remote` extra**, not a core dependency. Only the host
  and remote clients need it.

## Gotchas hit (relevant for the cross-machine phase)

- Pyro5 **won't expose classes named with a leading `_`** → broker classes are
  `NotificationBroker` / `ObserverCallback`.
- Pyro5 **rejects unknown `PYRO_*` env vars at import** → the broker location var
  is `HWLIB_DNC_URI`, not `PYRO_*`.
- Pyro5 **proxies are bound to one thread**; a daemon uses a threadpool. So: the
  broker creates each callback proxy **on the delivering thread**, and
  `ProxyDevice` calls `_pyroClaimOwnership()` per call.
- `serpent` (default serializer) **flattens tuples to lists** and can't move
  arbitrary types → `DeviceState` is sent as its `int` and rebuilt client-side;
  `position()` is coerced back to a tuple.

## Test status

- `testIsolatedDevice.py` — **6/6**: runs in its own process; methods forward
  automatically; common attributes read live; cross-process events via the DNC;
  child-process crash → `IsolatedDeviceError` while the caller survives; the same
  class in-process is the real device (`isinstance` holds).
- Full suite: **363 passed, 233 skipped, 0 failures**.
- The library still **imports and runs without Pyro5** (verified by blocking the
  import) → CI, which installs only `[dev]`, is unaffected (these tests skip).

## Limitations / caveats (prototype)

- **Same machine only.** The broker and device hosts run on localhost; discovery
  is via `HWLIB_DNC_URI` (the launcher starts the broker and exports it). No name
  server yet.
- **No auth.** Trusted-network assumption; the dispatcher allows any non-`_`
  method (no per-method whitelist).
- **Eager event bridge.** A host republishes *all* its notifications to the broker
  whether or not anyone observes (cheap on localhost; revisit for cross-machine).
- **`userInfo` fidelity.** Tuples arrive as lists (serpent); only `DeviceState`
  and position are coerced back.
- **Object identity = Pyro URI.** Works for devices; arbitrary `observedObject`s
  fall back to a process-local id that won't match across processes.
- **The broker is owned by whichever process calls `ensureBroker` first** (the
  launcher, for the prototype). Fine same-machine; cross-machine it should be a
  standalone service / NS-registered.

## Open questions / next steps

1. **Cross-machine:** register the broker and device URIs in the Pyro **name
   server**; `ensureBroker` becomes "find or start"; clients/hosts discover by
   broadcast with a `PYRO_NS_HOST` override (see the plan doc).
2. **Whitelist** remotely-callable methods if the network isn't trusted.
3. **Lazy event forwarding** (only forward observed notifications) if traffic
   matters.
4. **Auto-restart policy** for a crashed host (currently mark-dead).
5. Decide whether to **merge to `master`** as a checkpoint (CI runs on the PR;
   remoting tests skip without the `remote` extra) and whether to add a runnable
   `examples/remoting_example.py`.

## How to try it

```
pip install -e ".[remote]"     # installs Pyro5
python -m pytest hardwarelibrary/tests/testIsolatedDevice.py -v
```
Or interactively, the snippet under "What it does" above.
