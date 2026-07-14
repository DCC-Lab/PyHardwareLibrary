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

- Native USB on current eV revisions: the back-panel USB connector is a native
  USB-CDC port exposed by an STM32 micro-controller inside the eV (confirmed on
  the lab eV25s). It presents a virtual COM port to the host. Older eV revisions
  use a true RS-232 DB-9 instead, but the wire protocol is identical and looks
  like a serial port to the host either way. On macOS the portPath is
  `/dev/cu.usbmodem*` (USB-CDC); on Linux `/dev/ttyACM*`; on Windows a `COMn`.
  (A true-RS-232 unit reached through an external USB-serial adapter would
  instead show up under that adapter's driver, e.g. `/dev/cu.usbserial-*`.)
- The lab eV25s enumerates as **VID `0x0483`, PID `0x5740`** — STMicroelectronics'
  *generic* STM32 Virtual COM Port identity. Because that identity is shared by
  many unrelated STM32-based USB-CDC boards, the driver is still instantiated by
  `portPath` (like `CoboltDevice`) rather than discovered by VID/PID, to avoid
  binding to the wrong device. On a host that only ever has this one STM32 CDC
  port, VID/PID discovery can be enabled (see the note in
  `hardwarelibrary/sources/millennia.py`).
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
- **A `P:<f>` setpoint write can silently not take, since action commands have
  no reply.** Two distinct causes were pinned down on the lab eV25s:
  1. *Commit lag.* After `P:<f>` the eV needs roughly a second to commit the new
     setpoint; a `?PSET` read issued too soon returns the stale prior value.
     Wait ~1 s before reading back.
  2. *Mid-ramp rejection.* The eV refuses a setpoint change while the output is
     still ramping to the previous setpoint (confirmed: from a settled 23 W,
     `P:25.00` is accepted; issued again immediately while ramping, the next
     `P:23.00` is ignored and `?PSET` stays 25.00). This is a set-and-forget
     pump laser, so let the output settle before changing the setpoint again.
  The driver confirms the commands that matter: `doSetPower` writes, waits
  `settleDelay` (1 s), confirms against `?PSET`, retries, and raises
  `UnableToConfirmSetpoint` if it never takes; `doTurnOn`/`doTurnOff` do the
  same against `?D` and raise `UnableToConfirmState`. A throwaway read or brief
  settle is also wise right after a port re-open, where the first query can
  return stale data.

  > `doTurnOff` was verified on hardware: `OFF` drops `?D` to `0` and `?P` to
  > ~0 W immediately (the diodes cut, no slow ramp), so the confirm lands on the
  > first try. `turnOn` was confirmed only with the laser already on; a
  > cold-start turn-on (diodes warming up from off) has not been exercised, but
  > `?D` clearly tracks the *commanded* state at once rather than waiting for
  > emission, so the confirm path should hold there too. If a future cold start
  > shows `?D` lagging through warm-up, widen `confirmAttempts`/`settleDelay`.

## Commands implemented by the driver

| Capability | Action / query | Command | Reply |
|---|---|---|---|
| OnOffCapability | turn diodes on | `ON` | none |
| OnOffCapability | turn diodes off | `OFF` | none |
| OnOffCapability | diode emission state | `?D` | `1` (on) / `0` (off) |
| ShutterCapability | open shutter | `SHT:1` | none |
| ShutterCapability | close shutter | `SHT:0` | none |
| ShutterCapability | shutter state | `?SHT` | `1` (open) / `0` (closed) |
| PowerCapability | set output power (W) | `P:<f>` | none |
| PowerCapability | read output power (W) | `?P` | e.g. `4.90` (or `4.90 W` on some firmware) |
| (init only) | identification | `*IDN?` | comma-separated: manufacturer, model, serial, firmware |

`ON`/`OFF` gate the pump diodes; the shutter is a separate electromechanical
block in front of the output, so the laser can be on with the shutter closed.
The on/off state is read from `?D` (diodes), never from the shutter.

## Other documented commands (not yet wired into the driver)

All of the queries below were confirmed read-only on the lab eV25s
(2026-05-28); replies are the actual values observed.

| Function | Command | Reply |
|---|---|---|
| Read power setpoint (W) | `?PSET` (or `?PSET?`) | e.g. `25.00` (the commanded P:, vs ?P actual) |
| Set diode current (A) | `C1:<f>` | none |
| Read diode current (A) | `?C1` (or `?C`) | e.g. `9.120` |
| Laser-head serial number | `?SN` | e.g. `3239` |
| System fault/status string | `?F` | ASCII status, e.g. `System Ready` |
| Laser-head hours | `?HEADHRS` | e.g. `75.3` |
| Power-supply hours | `?PSHRS` | e.g. `592.8` |
| Diode/baseplate temperature (C) | `?T` | e.g. `24.25` |

There is no direct interlock query in the eV short command set; interlock /
fault state is reported only through `?F`.

Identification uses the SCPI-style `*IDN?` query, **not** the `?IDN` form that
appears in some Millennia documents. On the lab eV25s, `?IDN` is silently
ignored (returns nothing); `*IDN?` returns

    Spectra_Physics,Millennia eV,3239,214-00.004.096/CD00000019

i.e. manufacturer, model, **serial, firmware** (serial before firmware, the
reverse of the classic Millennia `?IDN` ordering). The driver parses these
positions; callers needing precise provenance should fall back to the raw
`self.idn` string. The bare serial number is also available directly via `?SN`.
