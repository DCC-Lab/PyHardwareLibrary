---
name: pyhardwarelibrary
description: Control lab hardware with the PyHardwareLibrary Python package — motion stages, spectrometers, lasers, power meters, DAQs, and oscilloscopes. Use when a user wants to move a stage, acquire a spectrum, turn a laser on/off or set its power/wavelength, read a power meter, read/write DAQ voltages, discover connected devices, run code without hardware (debug devices), or build a headless/GUI controller around a device. Covers the device lifecycle, per-family public API, event notifications, and the DeviceController worker-thread wrapper.
---

# Using PyHardwareLibrary

PyHardwareLibrary is a device-oriented library: every instrument is a `PhysicalDevice`
subclass with a uniform lifecycle and a small, predictable public API per family. This
skill is for *using* devices to get work done (move, measure, set). To *write a new
driver*, read `CLAUDE.md` and `README-4-New-device-coding-example.md` instead.

## The one rule: lifecycle

Every device follows the same pattern. Construct it, initialize it, use it, shut it down.

```python
from hardwarelibrary.motion.sutterdevice import SutterDevice

stage = SutterDevice()          # construct (does not touch hardware)
stage.initializeDevice()        # opens the port, raises on failure
try:
    stage.moveTo((1000, 2000, 0))
    print(stage.position())
finally:
    stage.shutdownDevice()      # always release the port
```

- `initializeDevice()` opens the connection and raises `PhysicalDevice.UnableToInitialize`
  if the device is absent/busy. Nothing works before it.
- `shutdownDevice()` closes the port. Always call it (use `try/finally`).
- Calling a command before `initializeDevice()` raises `PhysicalDevice.NotInitialized`.

## Finding / constructing a device

There is no reliable generic auto-discovery — do **not** rely on `PhysicalDevice.any()`
(it is incomplete and returns nothing). Use one of these instead:

- **Spectrometers have working discovery**: `Spectrometer.any()` returns the first
  supported spectrometer, ready to use.
- **Everything else: construct the concrete class directly.** USB devices match by
  serial number (default `None`/`"*"` = first found); serial/TCP devices take a port
  path. See each family below for the exact constructor.

## Run without hardware (debug devices)

Most families ship a `DebugXxxDevice` that emulates the protocol in memory, so examples
and tests run with nothing plugged in. They obey the same lifecycle and API.

```python
from hardwarelibrary.motion.linearmotiondevice import DebugLinearMotionDevice
from hardwarelibrary.daq.labjackdevice import DebugLabjackDevice
from hardwarelibrary.sources.millennia import DebugMillenniaEv25Device

stage = DebugLinearMotionDevice()
stage.initializeDevice()
stage.moveTo((10, 20, 30))
print(stage.position())         # (10, 20, 30)
stage.shutdownDevice()
```

## Family quick reference

### Linear motion stages — Sutter MP-285, Thorlabs (Kinesis)

Base: `LinearMotionDevice`. Positions are 3-tuples `(x, y, z)` in native steps.

```python
from hardwarelibrary.motion.sutterdevice import SutterDevice
stage = SutterDevice(serialNumber=None)      # first one found
# Thorlabs is not re-exported from motion/__init__; import from its module and
# install the extra:  pip install -e .[thorlabs]
# from hardwarelibrary.motion.thorlabs import ThorlabsKinesisDevice
# stage = ThorlabsKinesisDevice(serialNumber="...")
stage.initializeDevice()

stage.moveTo((x, y, z))                       # absolute, native steps
stage.moveBy((dx, dy, dz))                    # relative
pos = stage.position()                        # -> (x, y, z)
stage.home()

stage.moveInMicronsTo((x_um, y_um, z_um))     # micron helpers
stage.moveInMicronsBy((dx_um, dy_um, dz_um))
posUm = stage.positionInMicrons()

# Raster a sample: returns dicts {"index": (i, j), "position": (x, y, depth)},
# positions in microns relative to the current position.
for point in stage.mapPositions(width, height, stepInMicrons):
    stage.moveInMicronsTo(point["position"])
stage.shutdownDevice()
```

### Rotation stages — Intellidrive

Base: `RotationDevice`. Note `IntellidriveDevice(serialNumber)` requires the serial number.

```python
from hardwarelibrary.motion.intellidrivedevice import IntellidriveDevice
rot = IntellidriveDevice(serialNumber="...")
rot.initializeDevice()
rot.moveTo(angle)            # absolute, degrees
rot.moveBy(deltaTheta)       # relative
theta = rot.orientation()
rot.home()
rot.shutdownDevice()
```

### Spectrometers — Ocean Insight USB2000 / USB2000+ / USB4000 / USB650 / SAS

Base: `Spectrometer`. The public method *is* the hardware hook (no `do*` wrapper).

```python
from hardwarelibrary.spectrometers import Spectrometer

spectrometer = Spectrometer.any()             # discovery works here
spectrometer.initializeDevice()
spectrometer.setIntegrationTime(50)           # ms
spectrum = spectrometer.getSpectrum()         # numpy array, aligned to .wavelength
print(spectrometer.getSerialNumber())
spectrometer.saveSpectrum("scan.csv")         # wavelength + intensity columns
spectrometer.shutdownDevice()

# One-liner live view (initializes for you; needs matplotlib + Tk):
# Spectrometer.any().display()
```

### Laser sources — Cobolt, Spectra-Physics Millennia eV, Sirah Matisse

Base: `LaserSourceDevice` plus capability mixins. A device only has the methods of
the capabilities it declares — check the table.

| Capability | Methods |
|---|---|
| `OnOffControl` | `turnOn()`, `turnOff()`, `isLaserOn()`, `canTurnOn()` |
| `ShutterControl` | `openShutter()`, `closeShutter()`, `isShutterOpen()` |
| `PowerControl` | `setPower(watts)`, `power()` |
| `InterlockControl` | `interlock()` |
| `WavelengthControl` | `setWavelength(nm)`, `wavelength()`, `wavelengthRange()` |

```python
from hardwarelibrary.sources.millennia import MillenniaEv25Device

laser = MillenniaEv25Device(portPath="/dev/cu.usbmodemXXXX")
laser.initializeDevice()
laser.setPower(5.0)          # watts
laser.turnOn()
laser.openShutter()
print(laser.power(), laser.isLaserOn(), laser.isShutterOpen())
laser.closeShutter()
laser.turnOff()
laser.shutdownDevice()
```

- Cobolt: `CoboltDevice(portPath="COM3")` — OnOff + Power (+ autostart constraints; it
  may refuse `turnOn()` when autostart is on, raising `CoboltCantTurnOnWithAutostartOn`).
- Matisse: `MatisseDevice(...)` over TCP — `WavelengthControl` (`setWavelength`/`wavelength`)
  plus BiFi/etalon/piezo/scan methods.

### Power meters — Gentec-EO Integra

Base: `PowerMeterDevice`.

```python
from hardwarelibrary.powermeters import IntegraDevice
meter = IntegraDevice()
meter.initializeDevice()
meter.setCalibrationWavelength(800)       # nm
watts = meter.measureAbsolutePower()      # the read method
meter.shutdownDevice()
```

### DAQ — LabJack U3

Combines capability mixins: analog/digital in/out, plus hardware-timed input.

```python
from hardwarelibrary.daq.labjackdevice import LabjackDevice
daq = LabjackDevice()                      # serialNumber="*" -> first found
daq.initializeDevice()
v = daq.getAnalogVoltage(channel=0)        # read
daq.setAnalogVoltage(2.5, channel=1)       # write (U3 DACs are slow PWM)
bit = daq.getDigitalValue(channel=4)
daq.setDigitalValue(1, channel=5)
# Hardware-timed acquisition: daq.acquireWaveform(...) (AnalogInputStreamCapability)
daq.shutdownDevice()
```

### Oscilloscopes — Tektronix TDS

Instantiated directly (no family/driver split); methods are SCPI per instrument.

```python
from hardwarelibrary.oscilloscope import OscilloscopeDevice
scope = OscilloscopeDevice()
scope.initializeDevice()
# per-instrument SCPI methods / Channels enum
scope.shutdownDevice()
```

## Reacting to events (NotificationCenter)

Devices post Cocoa-style notifications (state changes, measurements, moves) instead of
requiring polling. Observe them from anywhere:

```python
from hardwarelibrary.notificationcenter import NotificationCenter
from hardwarelibrary.powermeters.powermeterdevice import PowerMeterNotification

def onMeasure(notification):
    print("power:", notification.userInfo)

NotificationCenter().addObserver(self, onMeasure, PowerMeterNotification.didMeasure)
# ... measurements now call onMeasure with the value in notification.userInfo
NotificationCenter().removeObserver(self)
```

Useful notification enums: `PhysicalDeviceNotification` (will/did initialize/shutdown,
status), `LinearMotionNotification` (willMove/didMove/didGetPosition),
`PowerMeterNotification.didMeasure`.

## Headless / GUI apps: DeviceController

For an app (GUI, long-running service) wrap the device in a `DeviceController`. It runs
**all** device access on one worker thread, so blocking calls never freeze a UI and port
access is serialized. It auto-reconnects and reports through `NotificationCenter`.

```python
from hardwarelibrary.devicecontroller import (
    DeviceController, DeviceControllerNotification as N)
from hardwarelibrary.notificationcenter import NotificationCenter
from hardwarelibrary.sources.millennia import MillenniaEv25Device

controller = DeviceController(MillenniaEv25Device(portPath="/dev/cu.usbmodemXXXX"))

NotificationCenter().addObserver(self, lambda n: print(n.userInfo), N.status)
controller.start()
controller.connect()

controller.submit(lambda device: device.turnOn())              # fire-and-forget
reading = controller.submit(lambda device: device.power()).result()  # query, returns a Future
# Do not block on .result() from a UI thread.

controller.stop()
```

`submit(action)` runs `action(device)` on the worker and returns a
`concurrent.futures.Future` carrying the result or the exception. Failures also post a
`commandFailed` notification; drops post `connectionLost`/`connectionFailed`.

## Gotchas

- **Always `initializeDevice()` before use, and `shutdownDevice()` after** — wrap in
  `try/finally`. A leaked open port blocks the next run with a "resource busy" error.
- **`PhysicalDevice.any()` / `anyDevice()` are incomplete** — only `Spectrometer.any()`
  returns a usable device. For other families, construct the concrete class.
- **`DeviceManager` is not fully operational** — prefer the per-family approach above.
- **No hardware? Use the `DebugXxxDevice`** for that family to develop and test.
- **The version is git-tag-derived** (`setuptools-scm`); read `CHANGELOG.md`, because
  API changes can land even when the minor version is unchanged.
