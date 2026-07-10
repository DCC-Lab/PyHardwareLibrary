# HOPS I2C protocol — decoded from a live capture

> HOPS docs, read in order: 1. Overview & Runbook -> 2. USB/DLL Protocol -> **3. I2C Wire Protocol**.

> **Use at your own risk — reverse-engineered without Coherent.** This was
> obtained by intercepting `CohrHOPS.dll`'s calls and dumping their parameters, to
> write a pure-Python driver without the proprietary, Windows-only DLL. Addresses
> and registers are confirmed from the capture; wiring and part types are inferred.

Decoded from `ftci2c_capture_readonly.log` (captured 2026-07-09 via the logging
`CohrFTCI2C.dll` proxy, read-only queries only) on the lab Genesis CX-Vis (G532).
This is the wire protocol underneath `CohrHOPS.dll` — what a native `pyftdi`
driver would replay. See `Coherent-HOPS-1-Overview-and-Runbook.md` for how the capture
was made, and `Coherent-HOPS-3-I2C-Circuit.svg` for a bus diagram of the devices
below (logical, reconstructed from this capture — not a verified board schematic).

## Transport

FTCI2C setup once at open: `I2C_InitDevice(divisor=599)`, `I2C_SetMode(mode=1)`
(STANDARD_MODE). Every access is a standard I2C "write register pointer, then
read N bytes" (`I2C_Read`, rType=2 = BLOCK_READ). In the FTCI2C control buffer,
byte 0 is the device address with the write bit; the remaining control bytes are
the register pointer written before the repeated-start read.

The HOPS supply is **not one chip** — it's several I2C devices on one bus:

| 7-bit addr | Ctrl byte 0 (W) | Role | Register addressing |
|---|---|---|---|
| 0x52 | 0xA4 | **Config/calibration + identity EEPROM** | 2-byte pointer `0x01 0xXX`, 1 byte per read |
| 0x48 | 0x90 | **ADC** (power, temperatures — raw counts) | 1-byte register, reads 2 bytes |
| 0x20 | 0x40 | status/GPIO port | 1-byte register (0x00/0x01), 1 byte |
| 0x22 | 0x44 | status/GPIO port | 1-byte register (0x00/0x01), 1 byte |
| 0x24 | 0x48 | status/GPIO port (keyswitch) | 1-byte register, 1 byte |
| 0x25 | 0x4A | status/GPIO port (shutter) | 1-byte register, 1 byte |

## EEPROM 0x52 (identity + calibration), page 0x01

Strings are read byte-by-byte until a NUL:

| Reg | Field | Bytes | Value |
|---|---|---|---|
| 0x0100.. | head type (`?HTYPE`) | `47 35 33 32 00` | "G532" |
| 0x0110.. | head ID (`?HID`) | `56 48 35 33 35 39 00` | "VH5359" |
| 0x0160.. | board rev (`?HBDREV`) | `44 45 00` | "DE" |

Calibration constants are 4-byte **IEEE-754 big-endian** floats:

| Reg | Bytes | Float |
|---|---|---|
| 0x0120 | `44 95 40 00` | 1194 |
| 0x0124 | `45 CA D0 00` | 6490 |
| 0x0128 | `43 73 00 00` | 243 |
| 0x012C | `46 29 E8 00` | 10874 |
| 0x0180 | `C0 8B 4F 35` | -4.35342 |
| 0x0184 | `3F E7 EF A0` | 1.812 |
| 0x0188 | `C2 30 C3 89` | -44.191 |

(Blocks repeat at 0x0130/0x0140/0x0150 and 0x0184/0x0188/0x018C — per-channel
gain/offset sets.) **These are the head calibration values.** A stray I2C write
to 0x52 corrupts them — this is the concrete reason not to poke the bus blind.

## Live signals — ADC 0x48 (raw counts, converted with the cal constants)

| `?` command | I2C read | raw | note |
|---|---|---|---|
| `?P` (power) | dev 0x48, reg 0xE4, 2 bytes | `00 00` | 0 (laser off); scaled to W via cal |
| `?TMAIN` | dev 0x48, reg 0x94, 2 bytes | `06 A0` | raw ADC; scaled to °C (see below) |

**TMAIN calibration** (two DLL-correlated points, captured 2026-07-09):
raw 1696 ↔ 32.222 °C and raw 1432 ↔ 39.773 °C — an **inverse** (NTC-like)
relationship. Two-point linear fit: **`T(°C) = -0.028602 · raw + 80.7315`**,
good over ~32–40 °C. (A one-point-through-origin guess is wrong — the slope is
negative. Widen with more points, or use the EEPROM cal floats, for a larger
range.) The **power** ADC read only has the (0 counts → 0 W) point so far; its
non-zero scale needs actual emission to calibrate.

So `CohrHOPS` reads all EEPROM cal floats at init, then converts ADC counts to
watts/°C. A native driver must reproduce that scaling (or read the cal block and
apply the same gain/offset).

## Status / faults — GPIO ports 0x20/0x22/0x24/0x25

Single-byte port reads whose bits the DLL combines:

| `?` command | reads | raw |
|---|---|---|
| `?SH` (shutter) | dev 0x25 reg 0x00 | `EC` |
| `?KSW` (keyswitch) | dev 0x24 reg 0x00 | `94` |
| `?FF` (fault) | dev 0x20 reg 0x01/0x00, 0x24 reg 0x01/0x00, 0x22 reg 0x01/0x00 | `DC D5 FA 94 0F 15` |

The DLL masks specific bits out of these port bytes (e.g. `?SH`->0, `?KSW`->1 on
this run). The exact bit map needs a few more captures with the shutter/keyswitch
toggled to pin down which bit is which.

## Write protocol (captured 2026-07-09, beam blocked)

Writes go to two devices that were not touched by reads:

### Power setpoint — DAC at 0x29 (ctrl byte 0x52), register 0xA0

`PCMD=<w>` writes a 16-bit big-endian code to device 0x29, register 0xA0
(`I2C_Write` wType=2 / PAGE_WRITE, 2 data bytes):

| `PCMD` | wdata |
|---|---|
| 0.5 W | `00 33` (=51) |
| 0.0 W | `00 00` |

~102 counts/W through the origin from these two points (single non-zero point,
so the offset/exact scale should be confirmed with a couple more setpoints, or
computed from the EEPROM cal floats). This is **not** the cal EEPROM (0x52) — so
setting power never risks the calibration.

### Discrete controls — GPIO expander at 0x25 (ctrl byte 0x4A)

A PCA9555-style 16-bit I/O expander: register **0x02 = output port**, **0x06 =
configuration/direction**. Each command writes 0x06 (make the pin an output) then
0x02 (drive it). The DLL uses a read-modify-write shadow, so a native driver
should read 0x02/0x06, flip only the target bit, and write back (never blast a
whole byte).

Output-port 0x02 bit map (derived from the deltas):

| Bit | Mask | Control | Meaning |
|---|---|---|---|
| 0 | 0x01 | shutter (`SHCMD`) | 1 = open, 0 = closed (only `SHCMD=0` captured; `=1` inferred) |
| 3 | 0x08 | remote (`REM`) | **active-low**: 0 = remote on, 1 = off |
| 5 | 0x20 | software switch (`KSWCMD`, emission enable) | 1 = on, 0 = off |

Captured output-port values: `REM=1`->E4, `KSWCMD=0`->C4, `KSWCMD=1`->E4,
`SHCMD=0`->E4 (bit0 already 0), `REM=0`->EC.

All writes returned status 0, and the run restored REM/PCMD/KSWCMD and left the
shutter closed (verified in the final-state read).

## Status of the reverse-engineering

- **Reads: mapped.** Identity/EEPROM reads are trivially replayable; ADC and GPIO
  reads are captured, pending the count->unit scaling and the status bit map.
- **Writes: captured** (see "Write protocol" above). Power = DAC 0x29 reg 0xA0;
  shutter/remote/enable = GPIO expander 0x25 bits 0/3/5. Remaining refinement:
  a few more `PCMD` points to nail the DAC scale/offset, and confirming `SHCMD=1`
  (shutter open) — deliberately not captured to keep the beam blocked.
- A native `pyftdi` driver is therefore feasible: pyftdi's `I2cController` does
  exactly "write pointer, read N bytes" on these addresses. The remaining work is
  the ADC scaling, the status bit map, and a write capture — not more transport
  reverse-engineering.
