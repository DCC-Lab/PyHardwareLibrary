"""Stream full Verdi-G / HOPS status over Coherent's CohrHOPS.dll (Windows/Linux).

Read-only: it does not change the laser state or take remote control (the front
panel stays usable). Unlike the native transport, the DLL path also reads all
four thermal-servo temperatures and the interlock/fault state.

Setup: place CohrHOPS.dll and CohrFTCI2C.dll (matching your Python's bitness)
next to hardwarelibrary/sources/hopsdll.py, or pass dllDirectory=... below.

Run:  python examples/verdig/status_monitor_dll.py [count]
"""
import datetime
import sys
import time

from hardwarelibrary.sources.hopsdll import HOPSDLLInterface


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else None
    interface = HOPSDLLInterface()             # or HOPSDLLInterface(dllDirectory=r"C:\dlls")
    interface.open()

    identity = interface.identity()
    print("Connected via CohrHOPS.dll: {0} (head {1}, s/n {2}, max {3:.3f} W)".format(
        identity["model"], identity["headType"], identity["serialNumber"],
        identity["maxPower"]))

    read = 0
    try:
        while count is None or read < count:
            diag = interface.diagnostics()     # includes the four servo temperatures
            temps = ("main={mainTemperature:.1f} SHG={shgTemperature:.1f} "
                     "BRF={brfTemperature:.1f} etalon={etalonTemperature:.1f}").format(**diag)
            faults = interface.faults()
            interlock = "ok" if interface.interlockOk() else "FAULT"
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print("{0}  {1} C  |  P={2:.3f} W  shutter={3}  emission={4}  interlock={5}{6}".format(
                stamp, temps, interface.getPower(),
                "open" if interface.shutterOpen() else "closed",
                "ON" if interface.emissionOn() else "off", interlock,
                ("  faults=" + ",".join(faults)) if faults else ""))
            read += 1
            if count is None or read < count:
                time.sleep(1.0)
    except KeyboardInterrupt:
        print()
    finally:
        interface.close()


if __name__ == "__main__":
    main()
