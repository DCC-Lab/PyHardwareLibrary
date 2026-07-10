# Runbook: controlling the Coherent "Verdi-G" / Genesis HOPS laser

> HOPS docs, read in order: **1. Overview & Runbook** -> 2. USB/DLL Protocol -> 3. I2C Wire Protocol.

How we got a lab "Verdi-G" laser under computer control, end to end, and how to
do it again. Written so a future session (human or AI) can reproduce it without
rediscovering the dead ends.

> **Use at your own risk — reverse-engineered without Coherent.** Everything here
> was obtained by reverse-engineering the Windows-only, proprietary `CohrHOPS.dll`:
> intercepting its calls and dumping the parameters, so a pure-Python macOS/Linux
> version could be written without the DLL. Thanks to
> https://github.com/AllenNeuralDynamics/coherent-lasers for the critical starting
> point.

**Design.** Everything goes through the HOPS (High Output Power Supply) — which
appears to be a general supply Coherent reuses across many systems — so the driver
is a single `VerdiGDevice` backed by either transport: the DLL (`HOPSDLLInterface`)
or pure-Python pyftdi I2C (`HOPSNativeInterface`). `VerdiGDevice` picks one and is
otherwise unaware of the details.

For the protocol details see `Coherent-HOPS-2-USB-and-DLL-Protocol.md`; for the driver see
`hardwarelibrary/sources/verdig.py` (`VerdiGDevice`) and its interfaces
`hopsnative.py` / `hopsdll.py`. This file is the *workflow*.

---

## TL;DR

1. The lab laser labelled "Verdi-G" is actually a **Coherent Genesis CX-Vis**
   (head type `G532`, 532 nm) on a **HOPS (High Output Power Supply)**. It is **not a serial
   device**: it enumerates as an FTDI FT2232 but is driven as bit-banged I2C, so
   nothing answers over a COM port at any baud.
2. The only sane way to talk to it is **Coherent's `CohrHOPS.dll`**, which
   exposes an ASCII command API over that binary transport.
3. `CohrHOPS.dll` is **Windows-only**, and the lab control machine is a **Mac**.
   The working arrangement: **Claude Code (on macOS) writes the code**, drops it
   into a folder that a **Parallels Windows VM** sees, and the DLL is **run in
   Windows** (via PowerShell, because the VM had no Python). Output files sync
   back to macOS, so Claude reads the results and iterates.
4. The DLL and Coherent's full software are **public** — links below.

---

## What the laser actually is

Query it and it tells you (this is the real recorded output):

```
?LASERMODEL -> Genesis CX-Vis
?HTYPE      -> G532
?HID        -> VH5359      (head serial)
CohrHOPS.dll version: 2.0.7
```

USB identity of the supply: FTDI **FT2232**, `VID 0x0403 / PID 0x6010`,
manufacturer `Coherent`, product string `HOPS Power Supply`, adaptor serial
`FTV5L9CA`. On macOS it appears as `/dev/cu.usbserial-FTV5L9CA0` and `...CA1`.

## Why it can't be driven as a serial port

The FT2232 enumerates as a virtual COM port, but the HOPS firmware does **not**
run it as a UART. It is driven in bit-banged / MPSSE **I2C** to an NXP micro-
controller in the supply, and the command set is exchanged as **binary frames**.
Consequence, confirmed on the bench with the laser powered and lasing: it returns
**zero bytes** to every serial probe — all bauds 9600–921600, every
databit/parity/stopbit combo, every line terminator — and the FTDI never even
flags a framing error (the RX line never toggles). Do not waste time on pyserial;
it is structurally impossible.

## The software: CohrHOPS.dll — where to get it

Coherent's own DLL, headers, demo, and full software package are mirrored
publicly by the Allen Institute's `coherent-lasers` project:

- **Repo:** https://github.com/AllenNeuralDynamics/coherent-lasers
- **Release with the binaries (v0.1.0):**
  https://github.com/AllenNeuralDynamics/coherent-lasers/releases/tag/v0.1.0
  - `CohrHOPS.dll` (64-bit):
    https://github.com/AllenNeuralDynamics/coherent-lasers/releases/download/v0.1.0/CohrHOPS.dll
  - `CohrFTCI2C.dll` (64-bit, dependency):
    https://github.com/AllenNeuralDynamics/coherent-lasers/releases/download/v0.1.0/CohrFTCI2C.dll
  - `OPLS.Software.V3.7.1.zip` (359 MB — Coherent's full package, contains the
    `CohrHopsDemo` with `main.c`, both 32- and 64-bit DLLs, and `.pdb` debug
    symbols):
    https://github.com/AllenNeuralDynamics/coherent-lasers/releases/download/v0.1.0/OPLS.Software.V3.7.1.zip
- **Header (API):**
  https://raw.githubusercontent.com/AllenNeuralDynamics/coherent-lasers/main/src/coherent_lasers/genesis_mx/hops/CohrHOPS.h
- **Genesis command tables (read/write command strings):**
  https://raw.githubusercontent.com/AllenNeuralDynamics/coherent-lasers/main/src/coherent_lasers/genesis_mx/commands.py

Coherent also distributes the same DLL on the **install CD/USB shipped with the
laser** and, in principle, via Coherent Support (their public Resources page is
JS-gated with no direct download). The GitHub mirror above is the reliable source.

Copies used in this work are kept locally in the repo at `scratch-hops/`
(`CohrHOPS.dll`, `CohrFTCI2C.dll`, `CohrHOPS.h`, `CohrHopsDemo_main.c`). These are
**vendor binaries — do not commit them** to the repo; treat `scratch-hops/` as a
local stash and gitignore/remove it before a PR.

Bitness matters: match the DLL to whatever runs it. The standalone release-asset
`CohrHOPS.dll` is **x86-64** (use it with 64-bit PowerShell/Python); the copy
inside `OPLS/CohrHopsDemo/Release` is 32-bit x86.

---

## The workflow that worked (macOS + Parallels Windows)

### Roles

- **macOS (Claude Code):** writes all the code and probe scripts; cannot run the
  DLL. Places deliverables in a folder the VM can see; reads back the results.
- **Windows VM (Parallels):** runs `CohrHOPS.dll` against the USB-attached laser.
- **Human:** does the few GUI actions the Parallels *Standard* edition blocks
  from the command line (start the VM, route the USB device, double-click a file).

### Why these exact choices

- **Parallels Standard edition** blocks host→guest automation: `prlctl start` and
  `prlctl exec` return *"available only in Parallels Desktop Pro/Business."* So
  the Mac side cannot start the VM or run commands inside it. (Pro, ~US $120/yr,
  would unlock full automation — not required.)
- **Shared Profile** (Parallels setting, was already on) maps the Mac home into
  the guest: the Mac `~/Desktop` appears in Windows as `C:\Mac\Home\Desktop`, and
  files the guest writes there sync back to macOS. This is the data bridge.
- **No Python in the guest** — Windows only had the Microsoft Store `python.exe`
  *stub* (prints "Python was not found"). So we drive the DLL with **PowerShell
  P/Invoke** (`Add-Type` + `DllImport`), which is always present on Windows.

### Step by step

1. **macOS (Claude):** build a package folder on the Mac Desktop, e.g.
   `~/Desktop/VerdiHOPS/python64/`, containing the 64-bit `CohrHOPS.dll` +
   `CohrFTCI2C.dll`, a PowerShell probe (`hops_probe.ps1`), and a launcher
   (`RUN_ME.bat`). Because Shared Profile is on, it appears in Windows at
   `C:\Mac\Home\Desktop\VerdiHOPS\python64`.
2. **Human:** start the **Windows 11** VM in Parallels.
3. **Human:** route the laser's USB to the guest — Parallels menu bar >
   **Devices > USB & Bluetooth > Coherent "HOPS Power Supply"**. When routed it
   disappears from macOS (`/dev/cu.usbserial-FTV5L9CA*` gone). Leave the
   FieldMaster power meter (also FTDI) on the Mac.
4. **Human:** in Windows, open that folder and **double-click `RUN_ME.bat`**.
5. **macOS (Claude):** read `hops_probe_output.txt` (and `run_log.txt`) from
   `~/Desktop/VerdiHOPS/python64/`. Iterate: edit the script on the Mac, have the
   human re-run, read again.

The launcher (`RUN_ME.bat`) runs the probe under PowerShell so no Python is
needed:

```bat
@echo off
pushd "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "hops_probe.ps1"
popd
echo Press any key to close...
pause >nul
```

The probe loads the DLL with P/Invoke, discovers the device, initializes the
handle, sends read-only queries, and writes the results to a file:

```powershell
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices; using System.Text;
public static class Cohr {
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] public static extern bool SetDllDirectory(string p);
  [DllImport("CohrHOPS.dll", CallingConvention=CallingConvention.StdCall)]
    public static extern int CohrHOPS_CheckForDevices([Out] ulong[] c, out uint nc, [Out] ulong[] a, out uint na, [Out] ulong[] r, out uint nr);
  [DllImport("CohrHOPS.dll", CallingConvention=CallingConvention.StdCall)]
    public static extern int CohrHOPS_InitializeHandle(ulong h, StringBuilder head);
  [DllImport("CohrHOPS.dll", CallingConvention=CallingConvention.StdCall)]
    public static extern int CohrHOPS_SendCommand(ulong h, string cmd, StringBuilder resp);
  [DllImport("CohrHOPS.dll", CallingConvention=CallingConvention.StdCall)]
    public static extern int CohrHOPS_Close(ulong h);
}
"@
[Cohr]::SetDllDirectory($PSScriptRoot) | Out-Null
$c=New-Object 'ulong[]' 20; $a=New-Object 'ulong[]' 20; $r=New-Object 'ulong[]' 20
[uint32]$nc=0;[uint32]$na=0;[uint32]$nr=0
[void][Cohr]::CohrHOPS_CheckForDevices($c,[ref]$nc,$a,[ref]$na,$r,[ref]$nr)
$h = if ($nc) {$c[0]} else {$a[0]}
$head=New-Object System.Text.StringBuilder 100
[void][Cohr]::CohrHOPS_InitializeHandle($h,$head)   # $head -> "G532"
$resp=New-Object System.Text.StringBuilder 100
[void][Cohr]::CohrHOPS_SendCommand($h,"?LASERMODEL",$resp)  # -> "Genesis CX-Vis"
[void][Cohr]::CohrHOPS_Close($h)
```

The full read-only probe (`hops_probe.ps1`) and the safe write-path validation
(`hops_writetest.ps1`, exercises `REM=`/`PCMD=` then restores, never opens the
shutter) live in `~/Desktop/VerdiHOPS/python64/`.

---

## Gotchas we hit (and the fixes)

- **`.bat` window flashes and closes / does nothing.** From a Parallels shared
  folder the script runs from a UNC path (`\\Mac\...`) where `cd /d` silently
  fails. Fix: use `pushd "%~dp0"` (maps a temp drive for UNC), log everything to
  a file, and end with `pause` so the window never vanishes unseen.
- **"Python not found."** `where python` found only `...WindowsApps\python.exe`,
  the Microsoft Store *alias stub*. Fix: don't rely on Python — use PowerShell
  P/Invoke (always present).
- **`BadImageFormat` / DLL won't load.** 32/64-bit mismatch, or `CohrFTCI2C.dll`
  / `FTD2XX.dll` missing. Fix: use 64-bit DLLs with 64-bit PowerShell; ensure the
  FTDI **CDM driver** (provides `FTD2XX.dll`) is installed (Windows usually
  auto-installs it when the device is routed).
- **No device found by the DLL.** The USB was not routed to the VM. Fix: route it
  in the Parallels Devices > USB menu; confirm it left macOS.
- **The FT2232 is bus-powered**, so its COM ports appear even with the laser
  supply switched off — port presence does not mean the laser is on.
- **Don't confuse the ports.** On the lab Mac: `usbmodem48F8834E39561` is a
  Millennia eV (STM32 `0x0483:0x5740`, `*IDN?` -> Spectra_Physics), `FTFDLOTS` is
  the FieldMaster meter, `FTV5L9CA0/1` is this Genesis/HOPS supply.

---

## The DLL API and command set (essentials)

`CohrHOPS.dll` exports 6 `extern "C"` functions (ctypes/P-Invoke friendly):

| Function | Purpose |
|---|---|
| `CohrHOPS_GetDLLVersion(char*)` | version string |
| `CohrHOPS_CheckForDevices(conn,&nc, add,&na, rem,&nr)` | USB discovery -> handles |
| `CohrHOPS_InitializeHandle(handle, char* headOut)` | detect head; returns e.g. `G532` |
| `CohrHOPS_SendCommand(handle, char* cmd, char* respOut)` | one ASCII command -> ASCII reply |
| `CohrHOPS_Close(handle)` | release |
| `CohrHOPS_OpenSerialPort(port, &handle)` | for RS-232 HOPS supplies (not used here) |

Command vocabulary (Genesis/HOPS): reads `?HID ?HTYPE ?LASERMODEL ?HH ?P ?PCMD
?PLIM ?C ?CLIM ?SH ?KSW ?KSWCMD ?REM ?CMODE ?INT ?FF ?TMAIN ?TSHG ?TBRF ?TETA`;
writes take a `CMD=` suffix: `PCMD=<W>` (power setpoint), `KSWCMD=<0|1>` (software
switch = emission enable), `SHCMD=<0|1>` (shutter), `CMODECMD`, plus `REM=<0|1>`
(remote control — must be `1` before writes take effect). Faults: `?FF` is a hex
bitmask (`0x0020`=interlock, `0x0200`=glue board, etc.). Full table in
`Coherent-HOPS-2-USB-and-DLL-Protocol.md`.

**Emission model** (no single on/off): needs hardware keyswitch (`?KSW`=1) +
cleared interlock + `REM=1` + `KSWCMD=1` + `PCMD>0`; the mechanical shutter
`SHCMD` gates the beam.

---

## The driver

`hardwarelibrary/sources/verdig.py` — `VerdiGDevice` (+ `DebugVerdiGDevice`), one
laser-source driver combining `OnOffControl` / `ShutterControl` / `PowerControl`
/ `InterlockControl`. It drives the bus through an interchangeable
`HOPSInterface`, chosen with `VerdiGDevice(interface="auto")` (native first, then
DLL), or forced with `"native"` / `"dll"` / an instance:

- `hopsnative.py` — `HOPSNativeInterface`: pure-Python pyftdi I2C, no DLL
  (macOS/Linux). Hardware-confirmed end to end on the lab unit; `interlock()` /
  `faults()` raise `HOPSInterface.NotSupported` until the `?FF` decode is done.
- `hopsdll.py` — `HOPSDLLInterface`: Coherent's `CohrHOPS.dll` (ASCII command
  set; Windows/Linux), with the ctypes binding `CohrHOPS`.

Tests: `hardwarelibrary/tests/testVerdiG.py` (debug + native-on-mock always
run; a hardware class skips when no laser is reachable).

---

## Verified on hardware (2026-07-09, lab Genesis CX-Vis)

- Read path (identity, power, interlock/faults, all temperatures/hours): OK.
- Write path `REM=1` and `PCMD=0.5` -> read back `?PCMD`=0.498 (head quantizes
  to ~2 mW, inside the driver's tolerance), `?P` stayed 0 (no emission, shutter
  closed), then restored. So the DLL interface's REM/PCMD/confirm logic is proven.
- **Not yet exercised on hardware (safety):** `KSWCMD` (emission enable) and
  `SHCMD` (shutter open). Verify with the beam blocked and interlock cleared.
- Note: at probe time `?FF`=`0x0220` — an active **interlock fault** (+ glue-board
  bit); the laser will not emit until that is cleared.

---

## Reproduce from scratch — checklist

1. Download `CohrHOPS.dll` + `CohrFTCI2C.dll` (64-bit) from the v0.1.0 release
   link above. Put them in `~/Desktop/VerdiHOPS/python64/` on the Mac with the
   probe scripts from this repo's package.
2. Start the Parallels Windows VM. (Standard edition: do it in the GUI.)
3. Route the Coherent "HOPS Power Supply" USB device to the VM. Ensure the FTDI
   CDM driver is installed in Windows.
4. In Windows, open `C:\Mac\Home\Desktop\VerdiHOPS\python64` and double-click
   `RUN_ME.bat` (read-only probe) — confirm `?LASERMODEL` / head type.
5. Read `hops_probe_output.txt` back on the Mac.
6. For control, either run PowerShell that calls the DLL (as above) in the guest,
   or run `VerdiGDevice(interface="dll")` (this library) inside the guest with a real Python +
   the DLLs. For emission, first clear the interlock and block the beam.
