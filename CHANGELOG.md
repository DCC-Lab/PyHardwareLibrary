# Changelog

Notable changes to PyHardwareLibrary, loosely following
[Keep a Changelog](https://keepachangelog.com/). Read this before upgrading:
API changes can land even when the minor version is unchanged.

## [Unreleased]

### Added
- `FieldMasterDevice` and `DebugFieldMasterDevice` (`powermeters/`): a driver
  for the Coherent FieldMaster GS laser power/energy meter over RS-232 via an
  FTDI adaptor (9600 8N1, LF terminator, `pw?`/`en?`/`wv?`/`v` commands). The
  meter has no USB identity of its own, so `classIdVendor`/`classIdProduct` are
  the generic FTDI values (0x0403/0x6001); disambiguate multiple FTDI adaptors
  with the adaptor `serialNumber` or an explicit `portPath`. Note: the meter
  only answers RS-232 while on its Home or Trend screen, and
  `initializeDevice` raises with that hint when it does not respond.

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
