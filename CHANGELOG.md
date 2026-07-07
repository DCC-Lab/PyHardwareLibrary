# Changelog

Notable changes to PyHardwareLibrary, loosely following
[Keep a Changelog](https://keepachangelog.com/). Read this before upgrading:
API changes can land even when the minor version is unchanged.

## [Unreleased]

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
