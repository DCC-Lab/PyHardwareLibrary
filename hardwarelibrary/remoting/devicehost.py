"""Subprocess entry point: host one Remotable PhysicalDevice behind a Pyro5 daemon.

Run as::

    python -m hardwarelibrary.remoting.devicehost \\
        --device-class hardwarelibrary.remoting.exampledevices.RemotableDebugStage

Constructs the device (which must mix in Remotable), registers it with a localhost
Pyro daemon, prints ``READY <uri>`` on stdout (the parent reads it), then serves
requests until the process is terminated.
"""
import argparse
import importlib
import json
import os

import Pyro5.api


def _importClass(dottedPath):
    moduleName, className = dottedPath.rsplit(".", 1)
    return getattr(importlib.import_module(moduleName), className)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-class", required=True,
                        help="Fully qualified Remotable device class to host")
    parser.add_argument("--kwargs", default="{}",
                        help="JSON object of keyword arguments for the constructor")
    arguments = parser.parse_args()

    deviceClass = _importClass(arguments.device_class)
    device = deviceClass(**json.loads(arguments.kwargs))

    daemon = Pyro5.api.Daemon(host="127.0.0.1")
    # The device serves itself: Remotable exposes callMethod/getAttribute, so no
    # servant wrapper is needed.
    uri = daemon.register(device)

    # If a central broker is configured (inherited via HWLIB_DNC_URI), republish
    # this device's notifications to it so remote observers receive them.
    if os.environ.get("HWLIB_DNC_URI"):
        from hardwarelibrary.remoting.distributednotificationcenter import bridgeDeviceToBroker
        bridgeDeviceToBroker(device, str(uri))

    print(f"READY {uri}", flush=True)
    daemon.requestLoop()


if __name__ == "__main__":
    main()
