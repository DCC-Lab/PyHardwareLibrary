"""HOPSDLLInterface: the HOPS transport backed by Coherent's CohrHOPS.dll.

Implements the transport-agnostic HOPSInterface (see verdig.py) by sending the
DLL's ASCII command set over its binary/I2C transport. Windows/Linux only;
raises HOPSInterface.Unavailable where the DLL cannot load (e.g. macOS).
"""

import ctypes
import os
import sys
from enum import IntEnum

from .verdig import HOPSInterface

MAX_DEVICES = 20
MAX_STRLEN = 100
_DLL_DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class HOPSStatus(IntEnum):
    OK = 0
    INVALID_HANDLE = -1
    INVALID_HEAD = -2
    INVALID_COMMAND = -3
    INVALID_DATA = -4
    I2C_ERROR = -5
    USB_ERROR = -6
    FTCI2C_DLL_FILE_NOT_FOUND = -100
    FTCI2C_DLL_FUNCTION_NOT_FOUND = -101
    FTCI2C_DLL_EXCEPTION = -102
    NXP_ERROR = -200
    RS232_ERROR = -300
    THREAD_ERROR = -400
    OTHER_ERROR = -999


class HOPSError(Exception):
    def __init__(self, function, status):
        self.function = function
        self.status = status
        try:
            name = HOPSStatus(status).name
        except ValueError:
            name = "UNKNOWN"
        super().__init__("{0} failed: {1} ({2})".format(function, status, name))


class CohrHOPS:
    """Thin ctypes binding to CohrHOPS.dll (the 6 exported functions)."""

    def __init__(self, dllDirectory=_DLL_DIRECTORY):
        if not sys.platform.startswith(("win", "linux")):
            raise HOPSInterface.Unavailable(
                "CohrHOPS.dll is Windows/Linux only; this is {0}.".format(sys.platform))
        self.dll = self._loadLibrary(dllDirectory)
        self._declareSignatures()

    @staticmethod
    def _loadLibrary(dllDirectory):
        if sys.platform.startswith("win"):
            if hasattr(os, "add_dll_directory") and os.path.isdir(dllDirectory):
                os.add_dll_directory(dllDirectory)
            os.environ["PATH"] = dllDirectory + os.pathsep + os.environ.get("PATH", "")
            name = "CohrHOPS.dll"
        else:
            name = "libcohrhops.so"
        path = os.path.join(dllDirectory, name)
        if not os.path.exists(path):
            raise HOPSInterface.Unavailable(
                "{0} not found in {1}. Provide CohrHOPS.dll and CohrFTCI2C.dll "
                "(matching your Python's bitness).".format(name, dllDirectory))
        try:
            return ctypes.CDLL(path)
        except OSError as error:
            raise HOPSInterface.Unavailable(
                "Could not load {0}: {1} (often a 32/64-bit mismatch or a missing "
                "CohrFTCI2C.dll).".format(path, error))

    def _declareSignatures(self):
        handleArray = ctypes.c_uint64 * MAX_DEVICES
        self._handleArrayType = handleArray
        self.dll.CohrHOPS_GetDLLVersion.argtypes = [ctypes.c_char_p]
        self.dll.CohrHOPS_CheckForDevices.argtypes = [
            handleArray, ctypes.POINTER(ctypes.c_uint32),
            handleArray, ctypes.POINTER(ctypes.c_uint32),
            handleArray, ctypes.POINTER(ctypes.c_uint32)]
        self.dll.CohrHOPS_InitializeHandle.argtypes = [ctypes.c_uint64, ctypes.c_char_p]
        self.dll.CohrHOPS_SendCommand.argtypes = [
            ctypes.c_uint64, ctypes.c_char_p, ctypes.c_char_p]
        self.dll.CohrHOPS_Close.argtypes = [ctypes.c_uint64]
        for fn in ("GetDLLVersion", "CheckForDevices", "InitializeHandle", "SendCommand", "Close"):
            getattr(self.dll, "CohrHOPS_" + fn).restype = ctypes.c_int32

    @staticmethod
    def _check(function, status):
        if status != HOPSStatus.OK:
            raise HOPSError(function, status)

    def version(self) -> str:
        buffer = ctypes.create_string_buffer(MAX_STRLEN)
        self._check("CohrHOPS_GetDLLVersion", self.dll.CohrHOPS_GetDLLVersion(buffer))
        return buffer.value.decode(errors="replace")

    def checkForDevices(self) -> list:
        connected = self._handleArrayType()
        added = self._handleArrayType()
        removed = self._handleArrayType()
        nConnected = ctypes.c_uint32(0)
        nAdded = ctypes.c_uint32(0)
        nRemoved = ctypes.c_uint32(0)
        self._check("CohrHOPS_CheckForDevices", self.dll.CohrHOPS_CheckForDevices(
            connected, ctypes.byref(nConnected), added, ctypes.byref(nAdded),
            removed, ctypes.byref(nRemoved)))
        handles = [connected[i] for i in range(nConnected.value)]
        handles += [added[i] for i in range(nAdded.value)]
        return sorted(set(h for h in handles if h))

    def initializeHandle(self, handle: int) -> str:
        headType = ctypes.create_string_buffer(MAX_STRLEN)
        self._check("CohrHOPS_InitializeHandle",
                    self.dll.CohrHOPS_InitializeHandle(ctypes.c_uint64(handle), headType))
        return headType.value.decode(errors="replace")

    def sendCommand(self, handle: int, command: str) -> str:
        response = ctypes.create_string_buffer(MAX_STRLEN)
        self._check("CohrHOPS_SendCommand", self.dll.CohrHOPS_SendCommand(
            ctypes.c_uint64(handle), command.encode(), response))
        return response.value.decode(errors="replace").strip()

    def close(self, handle: int):
        self._check("CohrHOPS_Close", self.dll.CohrHOPS_Close(ctypes.c_uint64(handle)))


class HOPSDLLInterface(HOPSInterface):
    """HOPS transport over CohrHOPS.dll (ASCII command set)."""

    name = "dll"
    powerSetpointTolerance = 0.02

    # ?FF fault bitmask; bits 0x0020/0x0100/0x0300 relate to interlocks.
    faultBits = {
        0x0008: "Main TEC error",
        0x0010: "LBO/BRF temperature not OK",
        0x0020: "Interlock fault",
        0x0100: "Shutter error",
        0x0200: "Glue board error",
        0x0800: "LDD at current limit",
    }
    interlockFaultBit = 0x0020

    diagnosticReads = {
        "headHours": ("?HH", float), "current": ("?C", float),
        "currentLimit": ("?CLIM", float), "powerLimit": ("?PLIM", float),
        "mainTemperature": ("?TMAIN", float), "shgTemperature": ("?TSHG", float),
        "brfTemperature": ("?TBRF", float), "etalonTemperature": ("?TETA", float),
        "fanSpeed": ("?FAN", int), "mode": ("?CMODE", int),
    }

    def __init__(self, serialNumber=None, dllDirectory=_DLL_DIRECTORY):
        self.serialNumber = serialNumber
        self.dllDirectory = dllDirectory
        self.lib = None
        self.handle = None

    def open(self):
        self.lib = CohrHOPS(self.dllDirectory)     # raises HOPSInterface.Unavailable if no DLL
        handles = self.lib.checkForDevices()
        if not handles:
            raise HOPSInterface.Unavailable("CohrHOPS found no HOPS device on USB.")
        self.handle = self._selectHandle(handles)
        self.lib.initializeHandle(self.handle)

    def _selectHandle(self, handles):
        if self.serialNumber is None:
            return handles[0]
        for handle in handles:
            self.lib.initializeHandle(handle)
            if self.lib.sendCommand(handle, "?HID") == self.serialNumber:
                return handle
        raise HOPSInterface.Unavailable("No HOPS head with serial {0}".format(self.serialNumber))

    def close(self):
        if self.lib is not None and self.handle is not None:
            self.lib.close(self.handle)
        self.lib = None
        self.handle = None

    def _query(self, command) -> str:
        return self.lib.sendCommand(self.handle, command)

    def identity(self) -> dict:
        return {
            "model": self._query("?LASERMODEL"),
            "headType": self._query("?HTYPE"),
            "serialNumber": self._query("?HID"),
            "maxPower": float(self._query("?PLIM")),
        }

    def getPower(self) -> float:
        return float(self._query("?P"))

    def powerSetpoint(self) -> float:
        return float(self._query("?PCMD"))

    def setPower(self, power: float):
        self.lib.sendCommand(self.handle, "PCMD={0:.4f}".format(power))
        echoed = self.powerSetpoint()
        if abs(echoed - power) > self.powerSetpointTolerance:
            raise HOPSError("PCMD setpoint confirm", HOPSStatus.INVALID_DATA)

    def emissionOn(self) -> bool:
        return self._query("?KSWCMD") == "1"

    def setEmission(self, on: bool):
        self.lib.sendCommand(self.handle, "KSWCMD={0}".format(1 if on else 0))

    def shutterOpen(self) -> bool:
        return self._query("?SH") == "1"

    def setShutter(self, isOpen: bool):
        self.lib.sendCommand(self.handle, "SHCMD={0}".format(1 if isOpen else 0))

    def remoteOn(self) -> bool:
        return self._query("?REM") == "1"

    def setRemote(self, on: bool):
        self.lib.sendCommand(self.handle, "REM={0}".format(1 if on else 0))

    def mainTemperature(self) -> float:
        return float(self._query("?TMAIN"))

    def faults(self) -> list:
        reply = self._query("?FF")
        code = int(reply, 16) if reply else 0
        return [text for bit, text in self.faultBits.items() if code & bit]

    def interlockOk(self) -> bool:
        reply = self._query("?FF")
        code = int(reply, 16) if reply else 0
        return (code & self.interlockFaultBit) == 0

    def diagnostics(self) -> dict:
        return {name: cast(self._query(command))
                for name, (command, cast) in self.diagnosticReads.items()}
