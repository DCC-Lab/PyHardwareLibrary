# Verdi-G / HOPS examples

Read-only monitors for a Coherent HOPS-supply laser (Genesis / Verdi-G). Both
stream once per second and stop on Ctrl-C. Neither takes remote control, so the
front-panel wheel keeps working while they run.

- `temperature_monitor_native.py` — main temperature over **native pyftdi I2C**
  (no DLL). macOS/Linux; needs pyftdi + libusb and the laser on this host.
- `status_monitor_dll.py` — full status (all four servo temperatures, power,
  shutter, emission, interlock/faults) over **Coherent's `CohrHOPS.dll`**.
  Windows/Linux; needs the DLLs (see `../../hardwarelibrary/manuals/`
  `Coherent-HOPS-2-USB-and-DLL-Protocol.md`).

For the full driver and the two transports, see
`hardwarelibrary/sources/verdig.py` (`VerdiGDevice`) and the `Coherent-HOPS-*`
docs under `hardwarelibrary/manuals/`.
