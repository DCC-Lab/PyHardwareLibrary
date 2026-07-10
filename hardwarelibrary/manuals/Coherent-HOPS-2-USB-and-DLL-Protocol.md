# Coherent HOPS USB Protocol (Genesis / Verdi G-C)

> HOPS docs, read in order: 1. Overview & Runbook -> **2. USB/DLL Protocol** -> 3. I2C Wire Protocol.

How to talk to a Coherent "HOPS" (High Output Power Supply) over USB. This is the transport
used by the Genesis OPSL heads and the **Verdi G- and C-series** -- *not* the
DB-9 ASCII RS-232 protocol of the classic Verdi V-series (a different product
line, not covered here or by this library).

## Why a HOPS supply looks dead over serial

A HOPS supply enumerates as an **FTDI FT2232** (`0x0403:0x6010`, USB manufacturer
`Coherent`, product `HOPS Power Supply`), so the OS attaches an FTDI VCP driver
and creates two `/dev/cu.usbserial-*` (or `COMn`) ports. **They answer nothing.**
The FT2232 is not run as a UART: Coherent drives it in **bit-banged / MPSSE I2C**
mode. The supply's **NXP microcontroller** sits on that I2C bus, and the laser
command set is exchanged as **binary frames** on the bus. So no baud rate, parity,
or terminator will ever elicit a reply on the COM port -- verified on the bench: a
powered, lasing Verdi G returned zero bytes across every baud 9600-921600, all
databit/parity/stopbit combinations, and every terminator, with the FTDI never
even flagging a framing error (the RX line never toggles).

This was established from Coherent's own `CohrHOPS.dll` and its debug symbols
(`.pdb`), which are public in Coherent's OPLS software package (the `CohrHopsDemo`
folder) and mirrored in the AllenNeuralDynamics `coherent-lasers` GitHub release.

## The stack

```
your code
  -> CohrHOPS.dll         ASCII command API; parses ASCII, builds binary frames
     -> CohrFTCI2C.dll    hardware-I2C path  --.
     -> (NXP bit-bang)    software-I2C path  --+--> FTD2XX.dll -> FT2232 -> I2C bus -> NXP uC -> laser head
```

The DLL's `.pdb` reveals an `NXP` class implementing I2C by hand over FTDI GPIO
(`SetClockLineHigh/Low`, `SetDataLineHigh/Low`, `GetDataLine`, `Start`, `Stop`,
`SendByte`, `GetByte`, `MasterAck`, `GetSlaveAck`, `ReadRegister`,
`WriteRegister`), and an `I2C` class for the hardware-assisted FTCI2C path. **Do
not reimplement this blindly**: stray writes on that bus can land on the head's
EEPROM/registers and damage the laser. Use the DLL.

## The DLL API

`extern "C"`, `__stdcall`, exported without name mangling -- ctypes-friendly. All
functions return `0` (OK) or a negative status; string buffers are 100 bytes.

| Function | Purpose |
|---|---|
| `CohrHOPS_GetDLLVersion(char* version)` | DLL version string |
| `CohrHOPS_CheckForDevices(conn,&nConn, added,&nAdd, removed,&nRem)` | USB discovery; returns handle arrays |
| `CohrHOPS_OpenSerialPort(const char* port, HANDLE* handle)` | for RS-232 HOPS supplies |
| `CohrHOPS_InitializeHandle(HANDLE, char* headTypeOut)` | detect head; returns head-type string, or `INVALID_HEAD` |
| `CohrHOPS_SendCommand(HANDLE, char* cmd, char* resp)` | one ASCII command/query -> ASCII response |
| `CohrHOPS_Close(HANDLE)` | release the handle |

Status codes: `0 OK`, `-1 INVALID_HANDLE`, `-2 INVALID_HEAD`, `-3 INVALID_COMMAND`,
`-4 INVALID_DATA`, `-5 I2C_ERROR`, `-6 USB_ERROR`, `-100..-102 FTCI2C_DLL_*`,
`-200 NXP_ERROR`, `-300 RS232_ERROR`, `-400 THREAD_ERROR`, `-999 OTHER_ERROR`.

Call order (from Coherent's `CohrHopsDemo/main.c`):
`CheckForDevices` -> `InitializeHandle` -> `SendCommand("?HID")` -> `Close`.

## Command vocabulary (HOPS/Genesis)

Queries: `?HTYPE`, `?LASERMODEL`, `?HID`, `?HBDREV`, `?P` (power), `?SH` (shutter),
`?KSW` (keyswitch), `?CMODE`, `?PLIM`, `?CLIM`, `?POWERUNITS`, `?FAN`, `?INT`,
`?ETAD`, `?MAIND`, `?TBRF`, ... Writable settings take a `CMD` suffix: `?PCMD`
(set power), `?SHCMD` (shutter), `?KSWCMD`, `?CMODECMD`, `?TMAINCMD`, etc. This is
distinct from the V-series `?P`/`?L`/`?S`/`P:`/`L:`/`S:` set.

## Getting the DLLs

Not committed here (vendor binaries, Windows-only, bitness-specific). Obtain from:

- the **install media that shipped with the laser** (the Verdi-G-capable build), or
- Coherent's public **OPLS software** package (`CohrHopsDemo` folder has
  `CohrHOPS.dll`, `CohrFTCI2C.dll`, `main.c`, and `.pdb` symbols), or
- the AllenNeuralDynamics **`coherent-lasers`** GitHub release assets.

Place `CohrHOPS.dll` and `CohrFTCI2C.dll` next to
`hardwarelibrary/sources/verdig.py`, matching your Python's bitness (the OPLS
`CohrHopsDemo/Release` DLL is 32-bit x86; the standalone release-asset build is
x86-64).

## Using it from this library

`VerdiGDevice` drives the laser; the DLL is one of its interchangeable transports
(`HOPSDLLInterface`), the native pyftdi I2C path (`HOPSNativeInterface`) the
other. Normally you just let it pick:

```python
from hardwarelibrary.sources.verdig import VerdiGDevice

laser = VerdiGDevice(interface="auto")   # native first, then the DLL
laser.initializeDevice()
print(laser.laserModel, laser.headType, laser.headSerialNumber)
laser.setPower(0.5); laser.turnOn(); laser.openShutter()
laser.shutdownDevice()
```

To force the DLL transport, use `VerdiGDevice(interface="dll")`. The low-level
ctypes binding to `CohrHOPS.dll` is `CohrHOPS` in `sources/hopsdll.py`; on macOS
constructing the DLL interface raises `HOPSInterface.Unavailable` (no DLL for the
platform), so `interface="auto"` falls through to native.

## Open question for the Verdi G specifically

The public `CohrHOPS.dll` builds inspected so far list only **Genesis** head types
(`Genesis CX-UV/CX-Vis`, `Genesis MX-MTM/STM`, `Invalid head`) and contain **no
"Verdi" strings**. So `InitializeHandle` may return `INVALID_HEAD` for a Verdi G,
meaning the Verdi-capable CohrHOPS build is the one on the laser's own CD. One run
of the snippet above on a Windows host with the laser attached settles it: if
`initializeHandle` succeeds and `?LASERMODEL` names the Verdi, this DLL works; if
it raises `INVALID_HEAD`, use the laser's shipped DLL instead. Either way the API
and this wrapper are unchanged -- only the DLL file differs.
