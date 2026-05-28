# Spectra-Physics Millennia eV Serial Command Reference

ASCII command set for the Spectra-Physics Millennia eV CW DPSS laser (532 nm),
the pump laser sold with the Sirah/Spectra-Physics Matisse Ti:Sapphire ring
laser. Use this as the spec for the driver in
`hardwarelibrary/sources/millennia.py`.

Sources: the Millennia eV User's Manual "Programming Reference Guide" appendix,
cross-checked against the working `savikhin-lab/millenia_ev` Python driver,
which is the most complete machine-readable description of the eV protocol
available.

> The eV dialect below is **not** the classic Millennia Pro / Pro-s / V dialect.
> The classic units use `SHUTTER:1` / `SHUTTER:0` / `?SHUTTER` and the `?STB`
> status byte; the V has no software shutter at all (manual lever). The eV uses
> the shorter `SHT:1` / `SHT:0` / `?SHT` and `?D`. Do not mix the two.

## Transport and identity

- Native USB on current eV revisions: the back-panel USB connector exposes a
  virtual COM port to the host (USB-CDC or an internal FTDI/CP210x bridge
  depending on the revision). Older eV revisions use a true RS-232 DB-9. Either
  way the wire protocol is identical and looks like a serial port to the host.
  On macOS the portPath is typically `/dev/cu.usbmodem*` (USB-CDC) or
  `/dev/cu.usbserial-*` (FTDI/CP210x); on Linux `/dev/ttyACM*` or
  `/dev/ttyUSB*`; on Windows a `COMn`.
- The unit's USB VID/PID has not been recorded here yet, so the driver is
  instantiated by `portPath` (like `CoboltDevice`) rather than discovered by
  VID/PID. Adding VID/PID discovery is a straightforward follow-up once the
  values for this lab's eV are captured.
- Serial settings: **115200 baud, 8 data bits, no parity, 1 stop bit** (115200
  is the eV default; it is field-configurable via a `BAUDRATE` command).

## Protocol

All commands and responses are ASCII.

- Commands are terminated by `<CR>`, `<LF>`, or both. The driver sends `<CR>`.
- Replies are terminated by `<CR><LF>`. The library's serial port reads up to
  `<LF>`; strip the trailing `<CR>`.
- **Action commands** (`ON`, `OFF`, `SHT:1`, `SHT:0`, `P:<f>`) execute silently
  and return no reply. **Queries** (`?...`) return one value line.
- Because actions return nothing, flush the input before each query to discard
  any stray bytes (power-up chatter, or an unread ack) before reading the
  reply.

## Commands implemented by the driver

| Capability | Action / query | Command | Reply |
|---|---|---|---|
| OnOffControl | turn diodes on | `ON` | none |
| OnOffControl | turn diodes off | `OFF` | none |
| OnOffControl | diode emission state | `?D` | `1` (on) / `0` (off) |
| ShutterControl | open shutter | `SHT:1` | none |
| ShutterControl | close shutter | `SHT:0` | none |
| ShutterControl | shutter state | `?SHT` | `1` (open) / `0` (closed) |
| PowerControl | set output power (W) | `P:<f>` | none |
| PowerControl | read output power (W) | `?P` | e.g. `4.90` (or `4.90 W` on some firmware) |
| (init only) | identification | `?IDN` | comma-separated: manufacturer, model, firmware, serial |

`ON`/`OFF` gate the pump diodes; the shutter is a separate electromechanical
block in front of the output, so the laser can be on with the shutter closed.
The on/off state is read from `?D` (diodes), never from the shutter.

## Other documented commands (not yet wired into the driver)

| Function | Command | Reply |
|---|---|---|
| Set diode current (A) | `C1:<f>` | none |
| System fault/status string | `?F` | ASCII status string |

There is no direct interlock query in the eV short command set; interlock /
fault state is reported only through `?F`.

`?IDN` field ordering varies by firmware (Millennia V puts firmware-rev before
serial; Pro-s puts head/PS serial info before software-rev). The driver does a
best-effort positional parse for the current lab unit (firmware
SW214-00.004.096 on an eV25s); callers needing precise provenance should fall
back to the raw `self.idn` string.
