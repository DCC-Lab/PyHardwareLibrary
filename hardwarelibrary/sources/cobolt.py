from hardwarelibrary.physicaldevice import *
from hardwarelibrary.communication import *
from hardwarelibrary.communication.commands import TextCommand
from hardwarelibrary.communication.debugport import TableDrivenDebugPort
from .lasersourcedevice import LaserSourceDevice

import re
import time
from threading import Thread, RLock

globalLock = RLock()

class CoboltCantTurnOnWithAutostartOn(Exception):
    pass

class CoboltDevice(PhysicalDevice, LaserSourceDevice):
    commands = {
        "GET_POWER": TextCommand(
            name="GET_POWER",
            text_format="pa?\r",
            replyPattern=r"(\d+\.\d+)",
            matchPattern=r"pa\?\r",
            responseTemplate="{power:0.4f}\r\n"),
        "GET_REQUESTED_POWER": TextCommand(
            name="GET_REQUESTED_POWER",
            text_format="p?\r",
            replyPattern=r"(\d+\.\d+)",
            matchPattern=r"p\?\r",
            responseTemplate="{requestedPower:0.4f}\r\n"),
        "SET_POWER": TextCommand(
            name="SET_POWER",
            text_format="p {0:0.3f}\r",
            replyPattern=r"OK",
            matchPattern=r"p (?P<value>\d+\.?\d+)\r"),
        "GET_ON_OFF": TextCommand(
            name="GET_ON_OFF",
            text_format="l?\r",
            replyPattern=r"(0|1)",
            matchPattern=r"l\?\r",
            responseTemplate="{isOn}\r\n"),
        "TURN_ON": TextCommand(
            name="TURN_ON",
            text_format="l1\r",
            replyPattern=r"OK",
            matchPattern=r"l1\r"),
        "TURN_OFF": TextCommand(
            name="TURN_OFF",
            text_format="l0\r",
            replyPattern=r"OK",
            matchPattern=r"l0\r"),
        "GET_SERIAL_NUMBER": TextCommand(
            name="GET_SERIAL_NUMBER",
            text_format="sn?\r",
            replyPattern=r"(\d+)",
            matchPattern=r"sn\?\r",
            responseTemplate="{serialNumber}\r\n"),
        "TURN_AUTOSTART_ON": TextCommand(
            name="TURN_AUTOSTART_ON",
            text_format="@cobas 1\r",
            replyPattern=r"OK",
            matchPattern=r"@cobas 1\r"),
        "TURN_AUTOSTART_OFF": TextCommand(
            name="TURN_AUTOSTART_OFF",
            text_format="@cobas 0\r",
            replyPattern=r"OK",
            matchPattern=r"@cobas 0\r"),
        "GET_AUTOSTART": TextCommand(
            name="GET_AUTOSTART",
            text_format="@cobas?\r",
            replyPattern=r"(0|1)",
            matchPattern=r"@cobas\?\r",
            responseTemplate="{autostart}\r\n"),
        "GET_INTERLOCK": TextCommand(
            name="GET_INTERLOCK",
            text_format="ilk?\r",
            replyPattern=r"(0|1)",
            matchPattern=r"ilk\?\r",
            responseTemplate="{interlock}\r\n"),
    }

    def __init__(self, bsdPath=None, portPath=None, serialNumber: str = None,
                 idProduct: int = None, idVendor: int = None):

        self.laserPower = 0
        self.requestedPower = 0
        self.interlockState = None
        self.autostart = None
        self.laserSerialNumber = None
        self.isOn = None

        if bsdPath is not None:
            self.portPath = bsdPath
        elif portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        PhysicalDevice.__init__(self, serialNumber, idVendor, idProduct)
        LaserSourceDevice.__init__(self)
        self.port = None

    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def autostartIsOn(self) -> bool:
        self.doGetAutostart()
        return self.autostart

    def turnAutostartOn(self):
        self.doTurnAutostartOn()

    def turnAutostartOff(self):
        self.doTurnAutostartOff()

    def doInitializeDevice(self):
        try:
            if self.portPath == "debug":
                self.port = self.DebugSerialPort()
            else:
                self.port = SerialPort(portPath=self.portPath)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port for serial '{0}'".format(self.portPath))

            self.port.open()
            self.doGetLaserSerialNumber()
            self.doGetAutostart()
            self.doTurnAutostartOn()
            self.doGetInterlockState()
            self.doGetPower()
        except PhysicalDevice.UnableToInitialize:
            if self.port is not None and self.port.isOpen:
                self.port.close()
            raise
        except Exception:
            if self.port is not None and self.port.isOpen:
                self.port.close()
            raise PhysicalDevice.UnableToInitialize()

    def doShutdownDevice(self):
        self.port.close()
        self.port = None
        return

    def doGetInterlockState(self) -> bool:
        cmd = CoboltDevice.commands["GET_INTERLOCK"]
        cmd.send(port=self.port)
        self.interlockState = bool(int(cmd.matchGroups[0]))
        return self.interlockState

    def doGetLaserSerialNumber(self) -> str:
        cmd = CoboltDevice.commands["GET_SERIAL_NUMBER"]
        cmd.send(port=self.port)
        self.laserSerialNumber = cmd.matchGroups[0]

    def doGetOnOffState(self) -> bool:
        cmd = CoboltDevice.commands["GET_ON_OFF"]
        cmd.send(port=self.port)
        self.isOn = (int(cmd.matchGroups[0]) == 1)
        return self.isOn

    def doTurnOn(self):
        if not self.doGetAutostart():
            CoboltDevice.commands["TURN_ON"].send(port=self.port)
        else:
            raise CoboltCantTurnOnWithAutostartOn()

    def doTurnOff(self):
        CoboltDevice.commands["TURN_OFF"].send(port=self.port)

    def doGetAutostart(self) -> bool:
        cmd = CoboltDevice.commands["GET_AUTOSTART"]
        cmd.send(port=self.port)
        self.autostart = (int(cmd.matchGroups[0]) == 1)
        return self.autostart

    def doTurnAutostartOn(self):
        CoboltDevice.commands["TURN_AUTOSTART_ON"].send(port=self.port)
        self.autostart = True

    def doTurnAutostartOff(self):
        CoboltDevice.commands["TURN_AUTOSTART_OFF"].send(port=self.port)
        self.autostart = False

    def doSetPower(self, powerInWatts) -> float:
        CoboltDevice.commands["SET_POWER"].send(port=self.port, params=powerInWatts)
        actualPower = 0
        acceptableDifference = 0.1 * powerInWatts
        for i in range(10): # It is not an error if we don't converge
            actualPower = self.doGetPower()
            if abs(actualPower - powerInWatts) < acceptableDifference:
                break
            else:
                time.sleep(0.1)
        return actualPower

    def doGetPower(self) -> float:
        cmd = CoboltDevice.commands["GET_POWER"]
        cmd.send(port=self.port)
        return float(cmd.matchGroups[0])

    class DebugSerialPort(TableDrivenDebugPort):
        def __init__(self):
            super().__init__(commands=CoboltDevice.commands)
            self.power = 0.1
            self.requestedPower = 0
            self.isOn = 0
            self.autostart = 1
            self.serialNumber = "123456"
            self.interlock = 1

        def process_command(self, name, params, endPointIndex):
            with globalLock:
                if name == "GET_POWER":
                    return {"power": self.power}
                elif name == "GET_REQUESTED_POWER":
                    return {"requestedPower": self.requestedPower}
                elif name == "SET_POWER":
                    requestedPower = float(params["value"])
                    process = Thread(target=increasePowerSlowlyInBackground,
                                     kwargs=dict(port=self,
                                                 endPower=requestedPower,
                                                 duration=1.0))
                    process.start()
                    return "OK\r\n"
                elif name == "GET_ON_OFF":
                    return {"isOn": self.isOn}
                elif name == "TURN_ON":
                    if self.autostart == 1:
                        return "Syntax error: not allowed in autostart mode\r\n"
                    self.isOn = 1
                    return "OK\r\n"
                elif name == "TURN_OFF":
                    self.isOn = 0
                    return "OK\r\n"
                elif name == "GET_SERIAL_NUMBER":
                    return {"serialNumber": self.serialNumber}
                elif name == "TURN_AUTOSTART_ON":
                    if self.autostart == 0:
                        self.isOn = 0
                    self.autostart = 1
                    return "OK\r\n"
                elif name == "TURN_AUTOSTART_OFF":
                    self.autostart = 0
                    return "OK\r\n"
                elif name == "GET_AUTOSTART":
                    return {"autostart": self.autostart}
                elif name == "GET_INTERLOCK":
                    return {"interlock": self.interlock}


def increasePowerSlowlyInBackground(port, endPower, duration):
    actualPower = port.power
    delta = (endPower - actualPower)/10.0
    for i in range(10):
        with globalLock:
            try:
                port.power = actualPower + delta * (i+1)
            except:
                print("Unable to set power")
        time.sleep(0.05)
    port.power = endPower
