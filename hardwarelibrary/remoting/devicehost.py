"""Subprocess entry point: host one PhysicalDevice behind a Pyro5 daemon.

Run as::

    python -m hardwarelibrary.remoting.devicehost \\
        --device-class hardwarelibrary.motion.linearmotiondevice.DebugLinearMotionDevice

Constructs the device, registers a DeviceServant with a localhost Pyro daemon,
prints ``READY <uri>`` on stdout (the parent reads it), then serves requests until
the process is terminated.
"""
import argparse
import importlib
import json

import Pyro5.api

from hardwarelibrary.remoting.deviceservant import DeviceServant


def _importClass(dottedPath):
    moduleName, className = dottedPath.rsplit(".", 1)
    return getattr(importlib.import_module(moduleName), className)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-class", required=True,
                        help="Fully qualified PhysicalDevice subclass to host")
    parser.add_argument("--kwargs", default="{}",
                        help="JSON object of keyword arguments for the constructor")
    arguments = parser.parse_args()

    deviceClass = _importClass(arguments.device_class)
    device = deviceClass(**json.loads(arguments.kwargs))
    servant = DeviceServant(device)

    daemon = Pyro5.api.Daemon(host="127.0.0.1")
    uri = daemon.register(servant)
    print(f"READY {uri}", flush=True)
    daemon.requestLoop()


if __name__ == "__main__":
    main()
