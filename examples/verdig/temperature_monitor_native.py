"""Stream the Verdi-G / HOPS main temperature over native pyftdi I2C (no DLL).

Read-only: it does not change the laser state or take remote control (so the
front panel stays usable). Works on macOS/Linux with the laser attached and
pyftdi + libusb available.

Run:  python examples/verdig/temperature_monitor_native.py [count]
On macOS, put the directory that holds libusb-1.0 on the loader path, e.g.:
  DYLD_LIBRARY_PATH=/opt/homebrew/lib python examples/verdig/temperature_monitor_native.py
"""
import datetime
import sys
import time

from hardwarelibrary.sources.hopsnative import HOPSNativeInterface


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    interface = HOPSNativeInterface()          # or HOPSNativeInterface(url="ftdi://...")
    interface.open()
    print("Verdi-G / HOPS main-temperature monitor (Ctrl-C to stop). "
          "Native calibration valid ~32-40 C.")
    read = 0
    try:
        while count is None or read < count:
            celsius = interface.mainTemperature()
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print("{0}   TMAIN = {1:6.2f} C".format(stamp, celsius))
            read += 1
            if count is None or read < count:
                time.sleep(1.0)
    except KeyboardInterrupt:
        print()
    finally:
        interface.close()


if __name__ == "__main__":
    main()
