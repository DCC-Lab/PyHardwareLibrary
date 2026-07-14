# CLAUDE.md

PyHardwareLibrary controls scientific hardware (motion stages, spectrometers, lasers, DAQs, power meters, oscilloscopes, cameras) used in the DCC/M Lab. Drivers live under `hardwarelibrary/<family>/<device>.py`.

This file is for AI-assisted contributors. Humans should read `README.md` and the numbered companion docs (`README-1-USB.md` through `README-7-Sutter-ROE-200.md`) first — they cover USB/RS-232 background, the new-device tutorial, and the existing device matrix.

## General instructions

- Always read the release notes to see if there was any change in the API, which may happen even if the version minor was not changed.

## Style

- **camelCase everywhere** for methods, attributes, and parameters.
- docstrings on all methods
- **No comments on obvious code.** Only add one when the *why* is non-obvious (a constraint, a workaround, a surprising invariant).
- **No inline `# what this does` comments.** Well-named identifiers do that job.
- **No emojis** in code, commit messages, or markdown.
- **No wildcard imports in new code.** The existing `from X import *` everywhere is technical debt, not convention. Use explicit imports.
- **Descriptive parameter names.** `text_format` over `text` when the value is a format string. `displacement` over `d`. Brevity is not a goal.

## Running things

- Always try to use a local virtual environment if present in `.venv`. Python can be `python3`, or in a venv `python`.
- Tests: `python3 -m pytest hardwarelibrary/tests/<file>.py -v`.
- Directory collection (`pytest hardwarelibrary/tests/`) now works: `pyproject.toml` sets `python_files = ["test*.py"]` and `testpaths = ["hardwarelibrary/tests"]`, so the `testFoo.py` naming is collected. (The historical "zero tests" gotcha — pytest's default `test_*.py` pattern not matching `testFoo.py` — is resolved.)
- Tests for hardware-dependent code must `skipTest(...)` when no hardware is attached — they must not fail. Pattern established in PRs #65 and #66; the `DebugLabjackDevice` tests (`tests/testLabjackU3.py`) and the library-presence `skipTest(...)` guards in `tests/test_pylablib_kinesis.py` are the cleanest references.
- CI runs the suite on push/PR via `.github/workflows/tests.yml`; Sphinx docs build and publish to ReadTheDocs (`.readthedocs.yaml`, `docs/`).

## Architecture

Core triad — all under `hardwarelibrary/`:

- `physicaldevice.py:PhysicalDevice` — abstract base (`abc.ABC`) for every device. Owns lifecycle (`initializeDevice` / `shutdownDevice`), state machine (`DeviceState`), port handle, and monitoring thread. The lifecycle hooks `doInitializeDevice` / `doShutdownDevice` are `@abstractmethod`, so a driver that omits either fails at instantiation rather than at call time.
- `devicemanager.py:DeviceManager` — singleton. Discovers connected USB devices, dispatches add/remove notifications.
- `notificationcenter.py:NotificationCenter` — Cocoa-style pub/sub. Devices post notifications on state changes and measurements.
- `devicecontroller.py:DeviceController` — headless, toolkit-agnostic wrapper around *any* `PhysicalDevice`. Owns a single worker thread through which all device access flows (submitted actions and the periodic status poll alike), so blocking calls never touch a UI thread and port access is serialized. `submit(action)` runs `action(device)` on that thread and returns a `concurrent.futures.Future`; `connect()`/`disconnect()` manage the link with optional auto-reconnect. Everything is reported through `NotificationCenter` (`DeviceControllerNotification`), so any front-end (Tk, Qt, CLI, a test) just observes. Use this instead of hand-rolling a thread per app.

Communication abstractions under `hardwarelibrary/communication/`:

- Always try to use the primitives of `CommunicationPort`
- `commands.py` — `Command` / `TextCommand` / `MultilineTextCommand` / `DataCommand` classes that bundle outgoing payload + reply parser.
- `debugport.py:DebugPort` — table-driven mock port. Used by the few devices that adopt the `commands` dict pattern.
- `serialport.py`, `usbport.py` — concrete port implementations.

## Device families

Each family has an **abstract base class**. A driver subclasses it and implements the `@abstractmethod` hooks below; forgetting one raises `TypeError` at instantiation, naming the missing method. These are the family hooks, on top of `doInitializeDevice` / `doShutdownDevice` inherited from `PhysicalDevice`.

| Family | Folder | Abstract base class | Required hooks to implement |
|---|---|---|---|
| Linear motion | `motion/` | `LinearMotionDevice` | `doMoveTo`, `doMoveBy`, `doGetPosition`, `doHome` |
| Rotation | `motion/` | `RotationDevice` | `doMoveTo`, `doMoveBy`, `doGetOrientation`, `doHome` |
| Power meter | `powermeters/` | `PowerMeterDevice` | `doGetAbsolutePower`, `doGetCalibrationWavelength`, `doSetCalibrationWavelength` |
| Spectrometer | `spectrometers/` | `Spectrometer` (`base.py`) | `getSpectrum`, `getSerialNumber` (here the public method *is* the hook; no `doXxx` wrapper) |
| Oscilloscope | `oscilloscope/` | `OscilloscopeDevice` | instantiated directly (Tektronix), no family/driver split; per-instrument SCPI methods |
| Camera | `cameras/` | `CameraDevice` | `doCaptureFrame` |
| Laser source | `sources/` | `LaserSourceDevice` (marker) + capability mixins (see below) | the `do*` hooks of whichever mixins the driver declares |
| DAQ | `daq/` | capability mixins (see below) | one method per mixin: `getAnalogVoltage` / `setAnalogVoltage` / `getDigitalValue` / `setDigitalValue` |

**Thorlabs linear motion** is a backend dispatcher: `ThorlabsDevice` (in `motion/thorlabs.py`) routes to `ThorlabsKinesisDevice`, which drives the stage through `pylablib`'s Kinesis support. The old FTDI path (`ThorlabsFTDIDevice`) was dropped. Install with the `thorlabs` extra (`pip install -e .[thorlabs]`).

Both the **DAQ and laser-source families use interface-segregated capability mixins** instead of one fat base class, because a device may implement any subset of the capabilities.

- DAQ (`daq/daqdevice.py`): `AnalogInputCapability` (`getAnalogVoltage`), `AnalogOutputCapability` (`setAnalogVoltage`), `DigitalInputCapability` (`getDigitalValue`), `DigitalOutputCapability` (`setDigitalValue`), plus `AnalogIOCapability` / `DigitalIOCapability` that combine each pair, and `AnalogInputStreamCapability` for hardware-timed acquisition. The `configure*` and `direction*` methods are optional no-op hooks. Example: `class LabjackDevice(PhysicalDevice, AnalogIOCapability, DigitalIOCapability, AnalogInputStreamCapability)`. Mixins carry the `*Capability` suffix; only instantiable hardware drivers are named `*Device`.
- Laser sources (`sources/capabilities.py`): `OnOffControl` (`turnOn`/`turnOff`/`isLaserOn`), `ShutterControl` (`openShutter`/`closeShutter`/`isShutterOpen`), `PowerControl` (`setPower`/`power`), `InterlockControl` (`interlock`), `AutostartControl`, `WavelengthControl` (`setWavelength`/`wavelength`), `DispersionControl`. Each exposes a public method that calls a `do*` abstract hook the driver implements. `LaserSourceDevice` is a thin marker base; the behavior comes from the mixins. Examples: `class CoboltDevice(LaserSourceDevice, OnOffControl, PowerControl, ...)`, `class MillenniaEv25Device(LaserSourceDevice, OnOffControl, ShutterControl, PowerControl)`, `class MatisseDevice(PhysicalDevice, WavelengthControl)`.

## Adding a new device

Reference implementation: `hardwarelibrary/daq/labjackdevice.py`. The pattern:

1. Subclass the family base (it already extends `PhysicalDevice`). For DAQ, combine `PhysicalDevice` with the capability mixins you need, e.g. `class FooDAQ(PhysicalDevice, AnalogIOCapability)`.
2. Set class attributes `classIdVendor` and `classIdProduct` (USB VID/PID, or the equivalent for serial-only devices).
3. Implement `doInitializeDevice` and `doShutdownDevice`. Keep them minimal — open the port, close the port.
4. Implement the family's abstract hooks (see the table). Omitting one raises `TypeError` at instantiation, so the class will not even construct until the contract is complete.
5. Add a companion `DebugXxxDevice(XxxDevice)` in the same file. Stub the hardware, store state in dicts. Use `classIdVendor = 0xFFFF` and a unique `classIdProduct >= 0xFFF0`.
6. Export both from the family's `__init__.py`.
7. Add a test file `hardwarelibrary/tests/testXxx.py`. Include a `TestDebugXxxDevice` class (always runs) and a `TestXxxDevice` class that skips when hardware is absent.

`README-4-New-device-coding-example.md` walks through this end-to-end for humans; the LabJack rewrite is the most current concrete example.

## Patterns to avoid

- **The `commands` dict on `PhysicalDevice` is half-finished.** Only `IntegraDevice` (`powermeters/integradevice.py`) and `EchoDevice` use it. For new devices, do not adopt this pattern — implement protocol bytes directly in your `do*` methods, the way `SutterDevice`, `CoboltDevice`, and `OISpectrometer` do. The `send-side-migration` branch was meant to complete the pattern; until it merges, treat it as experimental.
- **`spectrometers/oceaninsight.py`** is 967 lines and has known structural problems (duplicate exception classes, a `DebugSpectro` that doesn't inherit from `Spectrometer`, a duplicate `validateUSBBackend` whose macOS check is wrong). Do not copy from it. New spectrometers should subclass `spectrometers/base.py:Spectrometer` directly.
- **`from X import *` in new files.** Many existing modules do this; resist mirroring. It hides what's in scope and confuses static tooling.
- **No consumer-facing `typing.Protocol`s.** A prototype mirrored each family's public API as a `Protocol`, then it was dropped: the abstract base class is the type to use in hints (`def scan(stage: LinearMotionDevice)`), which keeps a single source of truth and avoids Protocol/class drift. The DAQ's former `AnalogIOProtocol` / `DigitalIOProtocol` are gone — use the ABC capability mixins.

## Branch hygiene

- The main branch is named `master`, not `main`.
- Open PRs against `master`. Prefer per-bug commits (each with a Problem/Solution body) over bundled commits — PR #74 is the template.

## Versioning and releases

- The version is **not** stored in a file — `setuptools-scm` derives it from the latest git tag (`pyproject.toml` has `dynamic = ["version"]`). `hardwarelibrary.__version__` reads it back at runtime.
- A release is cut by creating and pushing an annotated tag `vX.Y.Z`. That triggers `.github/workflows/publish.yml`, which builds the sdist/wheel, publishes to PyPI via Trusted Publishing (OIDC, no token), and creates a GitHub Release with auto-generated notes.
- Follow semver: new device/feature with no breakage → minor; fixes only → patch.
- Record API-affecting changes in `CHANGELOG.md` (Keep a Changelog format). Note the project's standing warning: **API changes can land even when the minor version is unchanged**, so the changelog and release notes are the source of truth, not the version number.

## Test running cheatsheet

```
python3 -m pytest hardwarelibrary/tests/ -v          # whole suite (collection now works)
python3 -m pytest hardwarelibrary/tests/testCommandRecognition.py -v
python3 -m pytest hardwarelibrary/tests/testPhysicalDevice.py -v
python3 -m pytest hardwarelibrary/tests/testTableDrivenDebugPort.py -v
python3 -m pytest hardwarelibrary/tests/testLabjackU3.py -v
python3 -m pytest hardwarelibrary/tests/testDeviceController.py -v
python3 -m pytest hardwarelibrary/tests/testThorlabs.py -v
```

Single test:
```
python3 -m pytest hardwarelibrary/tests/testLabjackU3.py::TestDebugLabjackDevice::testSetAndGetAnalogVoltage -v
```
