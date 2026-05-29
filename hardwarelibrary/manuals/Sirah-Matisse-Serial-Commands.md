# Sirah Matisse Serial / Remote Command Reference

Command set for the Sirah Matisse tunable laser. Reconstructed from the
pylablib reference driver (`pylablib/devices/Sirah/Matisse.py`, class
`SirahMatisse`), which is the most complete machine-readable description of the
protocol available locally. Use this as the spec when implementing a Matisse
driver in `hardwarelibrary/sources/`.

## Transport and identity

- USB / RS-232 (VISA): the legacy connection. Sirah USB IDs are VID `0x17E7`,
  PID `0x0102` (VISA address form `USB0::0x17E7::0x0102::<ID>::INSTR`).
- Network: the Matisse Commander server. The TCP port is configured in Matisse
  Commander, not fixed in the protocol, so it is supplied as part of the
  address.

## Protocol

SCPI-like text. A query is `CMD?`; a set is `CMD value`.

- Replies are prefixed with `:` and echo the command, e.g. a query of
  `MOTBI:POS` returns `:MOTBI:POS 12345`. Strip the leading `:` and the echoed
  command to recover the value.
- Errors are returned as `!ERROR <code>,<msg>`.
- Run/stop tokens (the value for any `*:CNTRSTA` and for `SCAN:STA`):
  `RUN` / `RU` / `TRUE` mean run; `STOP` / `ST` / `FALSE` mean stop.

### Framing

- Direct serial / USB: plain text with line terminators.
- Matisse Commander (network/TCP): each message is length-prefixed. A 4-byte
  big-endian unsigned length precedes the payload, in both directions, and
  there are no line terminators. The session is ended by sending
  `Close_Network_Connection`.

This length-prefixed framing is the case anticipated by
`hardwarelibrary/communication/tcpport.py`: a Matisse driver should subclass
`TCPPort` and override `readData` / `writeData` to add the 4-byte length frame,
leaving the connection handling untouched.

## Command reference

`?` denotes a query; "set" sends `CMD value`. R/W marks whether the value can be
read, written, or both; "action" is a command that takes no value.

### Session / identity

| Command | Type | Meaning |
|---|---|---|
| `IDN?` | query | device identity |
| `Close_Network_Connection` | action | end Matisse Commander TCP session |

### `DPOW` -- resonator / diode power

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `DPOW:DC` | R | float | resonator power |
| `DPOW:LOW` | R/W | float | low-level cutoff power |
| `DPOW:WAVTAB` | R | string | power waveform table |

### `TE` -- thin etalon lock

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `TE:DC` | R | float | thin-etalon reflex power |
| `TE:CNTRSTA` | R/W | run/stop | lock control status |
| `TE:CNTRSP` | R/W | float | setpoint |
| `TE:CNTRPROP` | R/W | float | P gain |
| `TE:CNTRINT` | R/W | float | I gain |
| `TE:CNTRAVG` | R/W | int | averaging |
| `TE:CNTRERR` | R | float | error signal |

### `MOTBI` -- birefringent filter motor (coarse wavelength)

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `MOTBI:POS` | R/W | int | absolute position |
| `MOTBI:WAVELENGTH` | R | float (nm) | birefringent filter wavelength (see note) |
| `MOTBI:STA` | R | int | status word (bit-parsed) |
| `MOTBI:MAX` | R | int | max position |
| `MOTBI:HOME` | action | -- | home |
| `MOTBI:HALT` | action | -- | stop |
| `MOTBI:CL` | action | -- | clear errors |

`MOTBI:WAVELENGTH?` is not in the pylablib command set but is present on
firmware 1.20: verified live 2026-05-25 against the lab Matisse TS (S/N
25-47-17), returning `7.981178e+02` (798.12 nm). The firmware likely exposes
further commands beyond pylablib's set; probe before assuming the list is
complete.

### `MOTTE` -- thin etalon motor (same verb set as `MOTBI`)

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `MOTTE:POS` | R/W | int | absolute position |
| `MOTTE:STA` | R | int | status word (bit-parsed) |
| `MOTTE:MAX` | R | int | max position |
| `MOTTE:HOME` | action | -- | home |
| `MOTTE:HALT` | action | -- | stop |
| `MOTTE:CL` | action | -- | clear errors |

### `PZETL` -- piezo etalon

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `PZETL:BASE` | R/W | float | baseline / DC position |
| `PZETL:AMP` | R/W | float | drive amplitude |
| `PZETL:SRATE` | R/W | 8k/32k/48k/96k | sample rate |
| `PZETL:OVER` | R/W | int | oversampling |
| `PZETL:CNTRSTA` | R/W | run/stop | feedback control status |
| `PZETL:CNTRPROP` | R/W | float | feedback P |
| `PZETL:CNTRAVG` | R/W | int | feedback averaging |
| `PZETL:CNTRPHSF` | R/W | int | feedback phase |

### `FEF` -- piezo etalon feedforward

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `FEF:AMP` | R/W | float | feedforward amplitude |
| `FEF:PHSF` | R/W | int | feedforward phase |

### `SPZT` -- slow piezo

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `SPZT:NOW` | R/W | float | DC position |
| `SPZT:CNTRSTA` | R/W | run/stop | lock control status |
| `SPZT:CNTRSP` | R/W | float | setpoint |
| `SPZT:LPROP` | R/W | float | lock P |
| `SPZT:LINT` | R/W | float | lock I |
| `SPZT:FRSP` | R/W | float | free-running P (newer firmware) |
| `SPZT:FPROP` | R/W | float | free-running P (older firmware fallback) |

### `FPZT` -- fast piezo

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `FPZT:NOW` | R/W | float | DC position (0-1) |
| `FPZT:CNTRSTA` | R/W | run/stop | lock control status |
| `FPZT:CNTRSP` | R/W | float | setpoint |
| `FPZT:LKP` | R/W | float | lockpoint |
| `FPZT:CNTRINT` | R/W | float | I gain |
| `FPZT:LOCK` | R | bool | locked? |

### `REFCELL` -- reference cell

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `REFCELL:NOW` | R/W | float | DC position (0-1) |
| `REFCELL:LLM` | R/W | float | waveform lower limit |
| `REFCELL:ULM` | R/W | float | waveform upper limit |
| `REFCELL:OVER` | R/W | int | oversampling |
| `REFCELL:MODE` | R/W | none/avg/min/max | waveform mode |
| `REFCELL:TABLE` | R | string | waveform table |

### `SCAN` -- wavelength scan

| Command | R/W | Kind | Meaning |
|---|---|---|---|
| `SCAN:STA` | R/W | run/stop | scan status |
| `SCAN:NOW` | R/W | float | scan position |
| `SCAN:DEV` | R/W | none/slow_piezo/ref_cell | scan device |
| `SCAN:MODE` | R/W | int (bits: falling, stop_lower, stop_upper) | scan mode |
| `SCAN:LLM` | R/W | float | lower limit |
| `SCAN:ULM` | R/W | float | upper limit |
| `SCAN:RSPD` | R/W | float | rise speed |
| `SCAN:FSPD` | R/W | float | fall speed |

## Motor status word (`MOTBI:STA` / `MOTTE:STA`)

The status integer packs a low status/error code with high status bits.

Status bits: bit 7 = error, bit 8 = moving, bit 9 = off, bit 10 =
invalid_position, bit 11 = limit_sw1, bit 12 = limit_sw2, bit 13 = home_sw,
bit 14 = manual.

Status codes (low 7 bits when the error bit is clear): `0x00` undefined,
`0x01` init, `0x02` idle, `0x03` button_pressed, `0x04` moving_short_manual,
`0x05` moving_long_manual, `0x06` deccel, `0x07` finishing, `0x08` moving_abs,
`0x09` moving_rel, `0x10` calc_accel_table.

Error codes (low 7 bits when the error bit is set): `0x00` none,
`0x01` undef_command, `0x02` frequency_out_of_range, `0x03` ramp_length_invalid,
`0x04` limit_sw, `0x05`/`0x06` hold_current_off, `0x07` position_out_of_range,
`0x08` ignored_because_running, `0x20` internal, `0x21` watchdog,
`0x22` memory_write_error, `0x23` checksum.
