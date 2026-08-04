# Changelog

Notable changes to PyHardwareLibrary, loosely following
[Keep a Changelog](https://keepachangelog.com/). Read this before upgrading:
API changes can land even when the minor version is unchanged.

## [Unreleased]

## [2.1.0] - 2026-08-04

### Added
- **Notifications on every capability.** Each capability owns a
  `<Capability>Notification` enum, reachable as its `notification` attribute, and
  every public method is wrapped in the new `@notifies(will=..., did=...)`
  decorator, so a driver gets notifications by implementing hooks and writing no
  notification code at all. An operation that changes the instrument posts
  `will<Stem>` then `did<Stem>`; a read (`doGet*`, `doReadStream`) posts only
  `did<Stem>`, to keep a voltage sampled in a loop at one notification instead of
  two. `Spectrometer` gets `SpectrometerNotification`, whose `getSpectrum` keeps a
  `will` because an acquisition takes an integration time.
  - `did*` is posted whether the operation succeeded or not, so a `will*` is always
    followed by its `did*` and there is no separate failure member to pair up. The
    exception is still **re-raised untouched**, since a driver's exception type is
    part of its contract, so a caller sees it exactly as before while an observer
    decides what to do from the payload.
  - `user_info` is a dict of the public method's arguments by name, plus `"result"`
    and `"error"`, exactly one of which is non-None.
  - Capabilities related by inheritance share one enum, so `notification` is the
    same object on all of them and the members are interchangeable:
    `AnalogInputCapability`, `AnalogOutputCapability`, `AnalogIOCapability` and
    `AnalogInputStreamCapability` all post `AnalogNotification`, and the digital
    trio posts `DigitalNotification` (17 enums for 22 capabilities). Members are
    keyed by identity, so without sharing an observer would have to know which
    variant a device mixed in.
  - Measured overhead on a read with no observer is ~1.6 us per call (~2.0 us with
    one observer), against millisecond-scale device I/O.
  - Removes the unused nested `AnalogInputStreamCapability.Notification`
    (`willAcquire` / `didAcquire`), which was never posted; the equivalent members
    are now `AnalogInputStreamNotification.willAcquireWaveform` / `didAcquireWaveform`.
- The family bases that already posted notifications now follow the same scheme,
  through the same `@notifies` decorator, and name their enum in a `notification`
  attribute like the capabilities do. **Breaking for observers**:
  - `PowerMeterNotification.didMeasure` is now `didGetAbsolutePower`, named after
    its hook like everywhere else.
  - `LinearMotionNotification` and `RotationMotionNotification` keep their grouped
    `willMove` / `didMove` (`moveTo`, `moveBy` and `home` are one operation to an
    observer), but the payload changed: `user_info` is now a dict carrying the
    method's arguments by name plus `"result"` and `"error"`, where it used to be
    the bare position, displacement or angle. A handler reading
    `notification.user_info` as a tuple must now read `user_info["position"]`,
    `user_info["displacement"]` or `user_info["angle"]`.
  - Every one of them now also reports failures: the `did*` is posted even when the
    driver raised, with the exception under `user_info["error"]`.
  - `Spectrometer` gained the `notification` attribute it was missing.
  - `CameraDeviceNotification` is left alone: a capture session is a different
    shape (`imageCaptured` fires per frame), not a will/did pair around one hook.
- **Contract-level argument validation on the capability public methods**, through a
  new `validate=` parameter on `@notifies` and a new `hardwarelibrary/validation.py`
  holding the shared `require*` checks. The validator runs before anything is posted,
  so a refused call announces nothing and a will/did pair still means the driver was
  invoked. **Breaking**: calls that used to be accepted silently now raise.
  - `acquireWaveform(sampleCount=0)` returned an empty acquisition; now `ValueError`.
    An empty `channels` list failed with `min() iterable argument is empty`; now it
    names the parameter.
  - `configureStream(sampleRate=-100)` was accepted; a rate must be positive, or
    `None` to say the clock is external. `sampleRate=0` no longer means "external":
    pass `None`, which is what the docstring always said.
  - `setDigitalValue("yes", channel)` set the line True; a logic level must be a bool
    (0 and 1 accepted). `setAnalogVoltage("2.5", channel)` now raises `TypeError`.
  - `setSensitivity(-1)` and `setTimeConstant(0)` were silently snapped to a step;
    both must be positive.
  - `setWavelength` and `setDispersion` are checked against the range the driver
    reports, so `matisse.setWavelength(50.0)` no longer drives the birefringent
    filter outside the installed optics' 700-1000 nm.
  - Outlets are checked against `doGetOutletCount()` in `OutletSwitchingCapability`
    and `DefaultOutletCapability`, so `PwrUSBDevice._validateOutlet` is gone and every
    future strip inherits the rule.
  - `setInputSource` and `setTriggerSource` accept anything their enum accepts
    (`setInputSource("Differential")`) and hand the driver a member.
  - Instrument-specific limits stay in the drivers, unchanged.
- **Every notified operation now requires an initialized device.** `@notifies` calls
  `validateReady()` before anything else, raising `PhysicalDevice.NotInitialized`
  unless the device is `Ready` and naming the operation, the class and the actual
  state. Previously such a call either failed deep inside the driver with
  `AttributeError: 'NoneType' object has no attribute ...` on a port that was never
  opened, or -- on a debug device -- answered as though the hardware had done it and
  posted a `did*` claiming success. The check runs before the `will` is posted, so a
  refused call announces nothing. `validateReady` is defined once, on
  `PhysicalDevice`, where the device lifecycle belongs; `capabilities.py` only calls
  it, so a class mixing in a capability without being a `PhysicalDevice` answers for
  readiness itself rather than silently skipping the check. Methods that only report what a model supports
  (`supportedInputSources`, `supportedSensitivities`, `supportedTimeConstants`,
  `supportedTriggerSources`, `outletCount`) are exempt via `requiresReady=False`,
  since a UI populates its menus before connecting.
- `allCapabilities()` in `hardwarelibrary/capabilities.py`: returns every capability
  mixin the library defines, in declaration order. It answers the library-wide
  question ("what can be expressed?"), where `PhysicalDevice.capabilities()` answers
  the per-device one ("what does this instrument support?"). Enumerating the module
  rather than walking `Capability.__subclasses__()` keeps the answer independent of
  which device modules happen to be imported, and excludes the drivers, which are
  `Capability` subclasses themselves.
- `capabilityInterface()` in `hardwarelibrary/capabilities.py`: describes one capability
  as `extends` / `publicAPI` / `hooks` lists of `CapabilityMember(name, signature,
  isAbstract)` tuples. The `do` prefix is what separates a hook from the public API,
  not abstractness: a hook that is optional, or that defaults to a composition of the
  others, is concrete. Members a parent capability declares are left to that parent.
- `python -m hardwarelibrary --capabilities` (`-c`): prints every capability with the
  methods it defines and the hooks a driver must implement, so the list never has to
  be maintained by hand.
- `hardwarelibrary/tests/testCapabilities.py`: covers `allCapabilities()` and
  `capabilityInterface()`, and enforces the invariant that every capability mixin is
  declared in `capabilities.py`, by comparing the module listing against a full walk
  of the `Capability` subclass graph.

### Changed
- **The public/`do*` template method pattern is now uniform across every capability.**
  The DAQ, lock-in and trigger capabilities used to declare their public method
  itself as the `@abstractmethod`; they now follow the same rule as every other
  family: `getXxx()` is concrete and calls `doGetXxx()`, and only the hook is
  abstract. This keeps the public method free for the argument validation,
  notifications and error handling to be added there. Affected:
  `AnalogInputCapability`, `AnalogOutputCapability`, `AnalogIOCapability`,
  `AnalogInputStreamCapability`, `PhaseLockedDetectionCapability`,
  `TriggerCapability`, `DigitalInputCapability`, `DigitalOutputCapability`,
  `DigitalIOCapability`.
  - **Callers are unaffected**: every public name and signature is unchanged.
  - **Driver authors must rename their implementations** to the `do*` hook, e.g.
    `getAnalogVoltage` -> `doGetAnalogVoltage`, `setDigitalValue` ->
    `doSetDigitalValue`, `configureStream` -> `doConfigureStream`,
    `softwareTrigger` -> `doSoftwareTrigger`, `supportedSensitivities` ->
    `doGetSupportedSensitivities`. A driver that misses one fails loudly at
    instantiation with `TypeError`, naming the missing hook. `LabjackDevice` and
    `SR830Device` (and their debug counterparts) were migrated.
  - `configureStream(channels, sampleRate=None, **parameters)` forwards extra
    keyword arguments to `doConfigureStream`, so instrument-specific options
    (the SR830's `sampleClock`, the LabJack's deprecated `scanRate`) still reach
    the driver through the shared public method.
- **`Spectrometer` follows the same pattern**: `getSpectrum()` and
  `getSerialNumber()` are now concrete and delegate to the abstract
  `doGetSpectrum()` / `doGetSerialNumber()`, which is the last place in the
  library where the public method was itself the hook. `getSpectrum(**parameters)`
  forwards keywords to the driver, so `getSpectrum(maxRequests=2, maxWait=0.05)`
  still reaches `OISpectrometer`. `OISpectrometer` was migrated; `DebugSpectro`
  is unaffected because it does not subclass `Spectrometer`.
  - **ACTION REQUIRED for the licenced StellarNet driver**, which is distributed
    encrypted and is not in this repository: rename its `getSpectrum` and
    `getSerialNumber` to `doGetSpectrum` and `doGetSerialNumber`. Until then
    `StellarNet()` raises `TypeError` for the missing hooks.
- `hardwarelibrary/tests/testCapabilities.py` now also asserts that no
  `PhysicalDevice` subclass in the library declares an abstract method outside its
  `do*` hooks, so the pattern is enforced for family base classes, not just mixins.
  `HOPSInterface` (`sources/verdig.py`) is deliberately exempt: it is a transport
  strategy behind `VerdiGDevice`, closer to `CommunicationPort` than to a device API.
- README: the supported-hardware table now lists every driver in the tree. It was
  missing `VerdiGDevice`, `FieldMasterDevice`, `SR830Device`, `PwrUSBDevice` and
  `StellarNet`, and carried the Millennia without its USB identity
  (`0x0483:0x5740`). Added a "Capabilities" section explaining the mixin pattern
  from first principles, and refreshed the class-hierarchy diagram, which was
  stale in the same way.

## [2.0.0] - 2026-07-24

Recorded after the fact: this release was tagged without a changelog entry.

### Changed
- **`NotificationCenter` now comes from the standalone `notifcenter` package** on
  PyPI, added as a dependency, rather than living in the library.
  `hardwarelibrary/notificationcenter.py` is deleted, and the 19 imports across the
  tree point at `from notificationcenter import ...`. `hardwarelibrary/__init__.py`
  re-exports the external package, so `from hardwarelibrary import
  NotificationCenter` keeps working.
- **The notification API is snake_case**, a clean break with no aliases, across
  roughly 286 call sites: `addObserver` -> `add_observer`, `postNotification` ->
  `post_notification`, `removeObserver` -> `remove_observer`, `observersCount` ->
  `observers_count`, and the keyword arguments and attributes `notificationName`,
  `observedObject`, `userInfo`, `notifyingObject` -> `notification_name`,
  `observed_object`, `user_info`, `notifying_object`. Any code observing a device
  must be updated; this is what made the release a major one. Note that the rest of
  the library remains camelCase -- the snake_case is the external package's
  convention, not a change of style here.

## [1.5.0] - 2026-07-22

### Added
- PowerStrip device family (`hardwarelibrary/powerstrips/`) plus its first driver
  `PwrUSBDevice` (and `DebugPwrUSBDevice`) for the PwrUSB / PowerUSB controllable
  power strip (USB HID `04d8:003f`, enumerates as "Simple HID Device Demo"). The
  family follows the interface-segregated capability-mixin pattern used by
  `sources/` and `daq/`: `PowerStripDevice` is a thin marker base over
  `PhysicalDevice`, and behaviour comes from `OutletSwitchingCapability`
  (`turnOutletOn`/`turnOutletOff`/`setOutletState`/`isOutletOn`/`outletCount`,
  outlets 1-based), `DefaultOutletCapability` (per-outlet power-on default
  state), and `CurrentMeteringCapability` (`current()` in A, `accumulatedCharge()`
  in Ah, `resetAccumulatedCharge()`), all in the shared
  `hardwarelibrary/capabilities.py`. The strip speaks a single-byte HID report protocol
  driven through a `HIDPort`; the protocol was reverse-engineered publicly and
  cross-checked against aarossig/pwrusbctl (Apache-2.0) and pwrusb.com, but the
  implementation is our own. Outlet state is cached on write because live
  readback is unreliable on this firmware.
- `HIDPort` (`hardwarelibrary/communication/hidport.py`): a `CommunicationPort`
  over a USB HID device, backed by hidapi (IOKit on macOS), alongside
  `SerialPort` and `USBPort`. Needed because an HID device the OS claims has no
  `/dev` node (so `SerialPort` cannot reach it) and cannot be claimed by libusb
  (so `USBPort` cannot either) -- notably on macOS, where `IOHIDFamily` owns the
  interface. hidapi is an optional dependency; install it with the new `pwrusb`
  extra (`pip install -e .[pwrusb]`), required to drive the strip.
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
  `SampleClock` move there too, and the acquisition notification enum is now
  nested as `AnalogInputStreamCapability.Notification`). Imports must point at
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
