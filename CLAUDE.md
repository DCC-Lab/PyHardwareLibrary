# CLAUDE.md

PyHardwareLibrary controls scientific hardware (motion stages, spectrometers, lasers, DAQs, power meters, oscilloscopes, cameras) used in the Côté lab. Drivers live under `hardwarelibrary/<family>/<device>.py`.

This file is for AI-assisted contributors. Humans should read `README.md` and the numbered companion docs (`README-1-USB.md` through `README-7-Sutter-ROE-200.md`) first — they cover USB/RS-232 background, the new-device tutorial, and the existing device matrix.

## Style

- **camelCase everywhere** for methods, attributes, and parameters.
- **No docstrings on obvious code.** Only add one when the *why* is non-obvious (a constraint, a workaround, a surprising invariant).
- **No inline `# what this does` comments.** Well-named identifiers do that job.
- **No emojis** in code, commit messages, or markdown.
- **No wildcard imports in new code.** The existing `from X import *` everywhere is technical debt, not convention. Use explicit imports.
- **Descriptive parameter names.** `text_format` over `text` when the value is a format string. `displacement` over `d`. Brevity is not a goal.

## Running things

- Python is `python3`, not `python`.
- Tests: `python3 -m pytest hardwarelibrary/tests/<file>.py -v`.
- Directory collection (`pytest hardwarelibrary/tests/`) currently returns **zero tests** because pytest's default `python_files` pattern is `test_*.py` and the files here are `testFoo.py`. Name files explicitly until `pyproject.toml` is updated.
- Tests for hardware-dependent code must `skipTest(...)` when no hardware is attached — they must not fail. Pattern established in PRs #65 and #66; the `DebugLabjackDevice` tests in PR on `labjack-rewrite` are the cleanest reference.

## Architecture

Core triad — all under `hardwarelibrary/`:

- `physicaldevice.py:PhysicalDevice` — abstract base (`abc.ABC`) for every device. Owns lifecycle (`initializeDevice` / `shutdownDevice`), state machine (`DeviceState`), port handle, and monitoring thread. The lifecycle hooks `doInitializeDevice` / `doShutdownDevice` are `@abstractmethod`, so a driver that omits either fails at instantiation rather than at call time.
- `devicemanager.py:DeviceManager` — singleton. Discovers connected USB devices, dispatches add/remove notifications.
- `notificationcenter.py:NotificationCenter` — Cocoa-style pub/sub. Devices post notifications on state changes and measurements.

Communication abstractions under `hardwarelibrary/communication/`:

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
| Laser source | `sources/` | `LaserSourceDevice` | `doTurnOn`, `doTurnOff`, `doSetPower`, `doGetPower`, `doGetOnOffState`, `doGetInterlockState` |
| DAQ | `daq/` | capability mixins (see below) | one method per mixin: `getAnalogVoltage` / `setAnalogVoltage` / `getDigitalValue` / `setDigitalValue` |

DAQ uses **interface-segregated capability mixins** instead of one base class, because a device may do any subset of read/write on analog/digital lines: `AnalogInputDevice` (`getAnalogVoltage`), `AnalogOutputDevice` (`setAnalogVoltage`), `DigitalInputDevice` (`getDigitalValue`), `DigitalOutputDevice` (`setDigitalValue`), plus `AnalogIODevice` / `DigitalIODevice` that combine each pair. The `configure*` and `direction*` methods are optional no-op hooks. A driver combines `PhysicalDevice` with the mixins it needs, e.g. `class LabjackDevice(PhysicalDevice, AnalogIODevice, DigitalIODevice)`.

## Adding a new device

Reference implementation: `hardwarelibrary/daq/labjackdevice.py`. The pattern:

1. Subclass the family base (it already extends `PhysicalDevice`). For DAQ, combine `PhysicalDevice` with the capability mixins you need, e.g. `class FooDAQ(PhysicalDevice, AnalogIODevice)`.
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
- `send-side-migration` has been unmerged for months — do not assume its changes are present on `master`. On `master`, `TextCommand` uses `self.text`, not `self.text_format`.
- Open PRs against `master`. Prefer per-bug commits (each with a Problem/Solution body) over bundled commits — PR #74 is the template.

## Test running cheatsheet

```
python3 -m pytest hardwarelibrary/tests/testCommandRecognition.py -v
python3 -m pytest hardwarelibrary/tests/testPhysicalDevice.py -v
python3 -m pytest hardwarelibrary/tests/testTableDrivenDebugPort.py -v
python3 -m pytest hardwarelibrary/tests/testLabjackU3.py -v
```

Single test:
```
python3 -m pytest hardwarelibrary/tests/testLabjackU3.py::TestDebugLabjackDevice::testSetAndGetAnalogVoltage -v
```
