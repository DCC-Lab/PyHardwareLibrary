# Changelog

Notable changes to PyHardwareLibrary, loosely following
[Keep a Changelog](https://keepachangelog.com/). Read this before upgrading:
API changes can land even when the minor version is unchanged.

## [Unreleased]

### Added
- `VerdiGDevice` (and `DebugVerdiGDevice`): a laser-source driver for the Coherent
  "HOPS" (High Output Power Supply) laser -- Genesis heads / Verdi G-C, e.g. the
  lab Genesis CX-Vis (head `G532`). A HOPS supply is not a serial device: its
  FTDI FT2232 (`0x0403:0x6010`) is driven as bit-banged I2C, with power DAC, ADC,
  shutter/enable GPIO, and the head identity/calibration EEPROM all on one I2C
  bus (see `manuals/Coherent-HOPS-*`). `VerdiGDevice` combines `OnOffCapability`,
  `ShutterCapability`, `PowerCapability`, and `InterlockCapability`, and drives the bus
  through an interchangeable `HOPSInterface`:
  - `HOPSNativeInterface` (`sources/hopsnative.py`): **pure-Python** pyftdi I2C,
    no DLL (macOS/Linux). Hardware-confirmed end to end on the lab unit
    (identity, on/off, shutter, remote, power setpoint, temperature). Its
    `interlock()`/`faults()` raise `HOPSInterface.NotSupported` until the `?FF`
    decode is reverse-engineered.
  - `HOPSDLLInterface` (`sources/hopsdll.py`): Coherent's `CohrHOPS.dll` (ASCII
    command set; Windows/Linux). Read + `REM`/`PCMD` write paths hardware-
    confirmed; `KSWCMD`/`SHCMD` per the DLL spec, not yet exercised.
  Selection: `VerdiGDevice(interface="auto")` tries native first, then the DLL;
  pass `"native"`/`"dll"`/an interface instance to force one. Protocol and I2C
  decode in `manuals/Coherent-HOPS-2-USB-and-DLL-Protocol.md` and
  `manuals/Coherent-HOPS-3-I2C-Wire-Protocol.md`.

### Changed
- **Breaking:** capability mixins across all families now use a uniform
  `*Capability` suffix, reserving `*Device` for instantiable hardware drivers.
  Public methods and behavior are unchanged; only the mixin class names change.
  Drivers subclassing these must update their base-class lists and imports.
  - DAQ: `AnalogInputDevice` -> `AnalogInputCapability`, `AnalogOutputDevice` ->
    `AnalogOutputCapability`, `AnalogIODevice` -> `AnalogIOCapability`,
    `AnalogInputStreamDevice` -> `AnalogInputStreamCapability`,
    `DigitalInputDevice` -> `DigitalInputCapability`, `DigitalOutputDevice` ->
    `DigitalOutputCapability`, `DigitalIODevice` -> `DigitalIOCapability`,
    `PhaseLockedDetectionDevice` -> `PhaseLockedDetectionCapability`,
    `TriggerableDevice` -> `TriggerCapability`.
  - Laser sources: `OnOffControl` -> `OnOffCapability`, `ShutterControl` ->
    `ShutterCapability`, `PowerControl` -> `PowerCapability`, `InterlockControl`
    -> `InterlockCapability`, `AutostartControl` -> `AutostartCapability`,
    `WavelengthControl` -> `WavelengthCapability`, `DispersionControl` ->
    `DispersionCapability`.
  - Power meters: `WavelengthCalibratable` -> `WavelengthCalibrationCapability`,
    `AutoScalable` -> `AutoScaleCapability`, `ScaleAdjustable` ->
    `ScaleCapability`.
- **Breaking:** all capability mixins are consolidated into a single module,
  `hardwarelibrary/capabilities.py`, and share one `Capability` base class (the
  per-family `sources/capabilities.py`, `powermeters/capabilities.py`, and
  `daq/daqdevice.py` are removed; the DAQ enums `InputSource`, `TriggerSource`,
  `SampleClock`, `DAQNotification` move there too). Imports must point at
  `hardwarelibrary.capabilities` (the family package `__init__`s still re-export
  their own mixins, so `from hardwarelibrary.daq import AnalogIOCapability` and
  the like keep working). `capabilities()` / `hasCapability()` are hoisted onto
  `PhysicalDevice`, so every device -- including DAQ drivers -- now supports
  capability introspection; the duplicated methods on `LaserSourceDevice` and
  `PowerMeterDevice` are gone (`LaserSourceDevice` is now a pure marker).

## [1.4.0] - 2026-07-08

### Added
- `SR830Device` (and `DebugSR830Device`): Stanford Research SR830 DSP lock-in
  amplifier over a Prologix GPIB-USB controller. It combines several capabilities:
  `AnalogInputStreamDevice` (the four rear-panel Aux A/D inputs via `OAUX?`, plus
  hardware-timed buffered acquisition of the demodulated outputs from the internal
  data buffer), `AnalogOutputDevice` (the four rear-panel Aux D/A outputs via
  `AUXV`), `PhaseLockedDetectionDevice` (X/Y/R/theta, reference frequency, signal
  input source, sensitivity, and time constant), and `TriggerableDevice` (the
  rear-panel TRIG IN). Enums: `AuxInput`, `AuxOutput`, `StreamChannel`,
  `InputSource`. `doInitializeDevice` self-discovers the Prologix among the
  connected FTDI adaptors by confirming `*IDN?`, and pins the adaptor's serial.
- `PrologixGPIBPort` (`hardwarelibrary/communication/`): a `SerialPort` subclass
  that speaks the Prologix GPIB-USB controller `++` protocol. GPIB instruments
  talk to it with the ordinary `readString`/`writeString` primitives; the `++read
  eoi` handshake is encapsulated in its `readString`.
- New DAQ capability contracts in `daq/daqdevice.py`: `PhaseLockedDetectionDevice`
  (lock-in / phase-locked detection), `TriggerableDevice` with the `TriggerSource`
  enum, and the `SampleClock` enum for stream sample clocking.

### Changed
- **Breaking:** `AnalogInputStreamDevice`: the sample-rate parameter of
  `configureStream`/`acquireWaveform` is renamed `scanRate` -> `sampleRate`.
  Callers passing it positionally are unaffected; callers passing `scanRate=` by
  keyword must switch to `sampleRate=`. `LabjackDevice.configureStream` keeps
  `scanRate` as a temporary deprecated synonym, so LabJack callers are unaffected
  for now.
- `LabjackDevice` now imports `u3` (LabJackPython) lazily at point of use, so
  `import hardwarelibrary.daq` (and the new SR830 driver) works on hosts that do
  not have LabJackPython installed.

## [1.3.3] - 2026-07-08

### Changed
- Heavy third-party modules are now imported lazily, at their point of use,
  instead of at module load. `import hardwarelibrary` no longer pulls in
  `matplotlib` or `numpy` (import time drops from ~336 ms to ~59 ms); they load
  only when a plot is drawn or a spectrum is acquired. Affected: the
  spectrometers package (`SpectraViewer` deferred into `display()`/`displayAny()`,
  `numpy` into the methods that use it; `base.py` uses
  `from __future__ import annotations` for its `-> np.array` hint),
  `OscilloscopeDevice.displayWaveforms`, and the cameras module (`cv2`). Public
  APIs are unchanged. Two behavioral notes: importing `hardwarelibrary.cameras`
  no longer prints a warning when OpenCV is absent — a missing `cv2` now raises
  `ModuleNotFoundError` when a camera operation is invoked; and the unused
  matplotlib import block in `oceaninsight.py` was removed.

### Removed
- Dead `from pyftdi.ftdi import Ftdi` imports in `SutterDevice` and `EchoDevice`
  (both were unused and flagged `# FIXME: should not be here`). FTDI access still
  goes through `SerialPort`, which owns the `pyftdi` dependency.

## [1.3.2] - 2026-07-07

### Added
- `MillenniaEv25Device` (and its `MillenniaDevice` alias) now discovers its port
  by USB identity when constructed without a `portPath`. The class carries the
  STM32 Virtual COM Port identity `classIdVendor = 0x0483` /
  `classIdProduct = 0x5740`, and `doInitializeDevice` matches it over pyserial's
  ports, raising `UnableToInitialize` naming the identity when none is found. An
  explicit `portPath` still takes precedence, and a `serialNumber` narrows
  discovery when several STM32 USB-CDC ports are present. Note: `0x0483:0x5740`
  is STMicro's generic STM32 VCP identity shared by unrelated STM32 boards, so
  pin `portPath` on a host that has more than one.

## [1.3.1] - 2026-07-06

### Added
- Power-meter capability mixins (`powermeters/capabilities.py`), mirroring the
  laser-source `Capability` structure: `WavelengthCalibratable`
  (`getCalibrationWavelength` / `setCalibrationWavelength`), `AutoScalable`
  (`autoScaleIsOn` / `turnAutoScaleOn` / `turnAutoScaleOff`), and
  `ScaleAdjustable` (`getScale` / `setScale` / `availableScales`), each
  delegating to `do*` hooks the driver implements. `PowerMeterDevice` gains
  `capabilities()` and `hasCapability(capabilityClass)` for introspection.

### Changed
- The wavelength-calibration hooks (`doGetCalibrationWavelength`,
  `doSetCalibrationWavelength`) and their public methods move off
  `PowerMeterDevice` into the new `WavelengthCalibratable` mixin. The base now
  requires only `doGetAbsolutePower`. `IntegraDevice` and `FieldMasterDevice`
  declare `WavelengthCalibratable`, so their public API is unchanged; a new
  power meter that calibrates by wavelength must now mix in
  `WavelengthCalibratable` to expose those methods.
- `PhysicalDevice.__init__` is now a cooperative base: it calls
  `super().__init__()` after consuming the device-identity arguments, so a
  capability mixin combined with a device (e.g.
  `IntegraDevice(PowerMeterDevice, WavelengthCalibratable)`) has its `__init__`
  run instead of being skipped by the MRO. A mixin `__init__` must therefore
  take no required arguments and call `super().__init__()` itself. No existing
  device changes behavior.

## [1.3.0] - 2026-07-06

### Added
- `FieldMasterDevice` and `DebugFieldMasterDevice` (`powermeters/`): a driver
  for the Coherent FieldMaster GS laser power/energy meter over RS-232 via an
  FTDI adaptor (9600 8N1, LF terminator, `pw?`/`en?`/`wv?`/`v` commands). The
  meter has no USB identity of its own, so `classIdVendor`/`classIdProduct` are
  the generic FTDI values (0x0403/0x6001); disambiguate multiple FTDI adaptors
  with the adaptor `serialNumber` or an explicit `portPath`. The message
  terminator is a front-panel Menu setting (LF/CR/CR-LF); `initializeDevice`
  probes with the configured `terminator` (default LF) and falls through the
  other combinations until one replies, so a mismatched Menu self-heals. Note:
  the meter only answers RS-232 while on its Home or Trend screen, and
  `initializeDevice` raises with that hint when none of the terminators reply.
- `SerialPort.genericSerialConverterPorts()` and `isGenericSerialConverter()`,
  plus the `genericSerialConverterVendors` table: discover connected ports that
  come from a generic USB/RS-232 converter chip (FTDI, Prolific, Silicon Labs
  CP210x, WCH CH34x), so an instrument with no USB identity of its own can be
  located and disambiguated by the adaptor's serial number.
- `PhysicalDevice.usesGenericSerialConverter` flag (default `False`). A device
  behind a generic converter matches any converter vendor (its `vidpids()`
  expands to the whole table, product id wildcarded), and
  `DeviceManager.candidateClassesForAutoDiscovery()` excludes such classes from
  automatic probing, since their VID/PID identifies only the cable. FieldMaster,
  oscilloscope, Echo and IntelliDrive are flagged and must be constructed
  explicitly; Thorlabs (custom-EEPROM FTDI PID) stays a specific identity.

### Changed
- `PhysicalDevice.isCompatibleWith` treats a `None` product id in a `vidpids()`
  pair as a wildcard that matches any product from that vendor. Concrete
  `(vendor, product)` pairs are unaffected.

### Fixed
- `OISpectrometer.getSpectrum` no longer hangs. The wait for the "spectrum
  ready" flag is now bounded (`maxRequests`/`maxWait`) and raises
  `SpectrumRequestTimeoutError` instead of re-requesting a spectrum forever on a
  transient USB glitch; transient `usb.core.USBError` (incl. `USBTimeoutError`)
  during polling is absorbed and retried. `integrationTime` remains the first
  optional argument, so all existing callers are unaffected.

## [1.1.0] - 2026-05-29

### Changed
- `CommunicationPort`: the optional matching-method argument `alternatePattern`
  is renamed to `errorPattern` on `writeStringExpectMatchingString`,
  `writeStringReadMatchingGroups`, `writeStringReadFirstMatchingGroup`, and
  `readMatchingGroups`, and it now actually works on all of them (it was
  inverted in one method and silently ignored in the others). A reply matching
  `errorPattern` raises `CommunicationReadError` carrying that pattern's capture
  groups; a reply matching neither pattern still raises
  `CommunicationReadNoMatch`. Callers that passed the argument positionally are
  unaffected; callers passing `alternatePattern=` by keyword must switch to
  `errorPattern=`.
- `CommunicationReadError.__init__` now takes `(reply, groups)` instead of a
  single argument. Catching the exception is unaffected; only code that
  constructs or raises it directly must update.
- `MatisseDevice.queryString` is renamed to `query`. The high-level API
  (`wavelength`, `setWavelength`, the BiFi/thin-etalon/piezo/scan get/set/lock
  methods, and `sendSetting`) is unchanged.

### Added
- `CommunicationReadError` exception (replaces `CommunicationReadAlternateMatch`).
- `CommunicationPort.writeStringReadMatch` and `CommunicationPort.matchReply`,
  the shared write-then-read-then-match and pure-match helpers the matching
  methods now delegate to.
- `DebugMatissePort`, a debug port that speaks the Matisse reply grammar so
  `DebugMatisseDevice` runs the same port code path as the real device.

### Removed
- `MatisseDevice.parseReply`. Its job is now expressed as the port's
  `replyPattern`/`errorPattern`, with errors mapped to `MatisseCommanderError`.

### Deprecated
- `CommunicationReadAlternateMatch` is kept as an alias for
  `CommunicationReadError` and will be removed in a future release.
