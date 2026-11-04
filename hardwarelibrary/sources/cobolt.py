from hardwarelibrary.communication.debugport import ProtocolDebugPort
from hardwarelibrary.communication.protocol import CommandDictionary
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.physicaldevice import PhysicalDevice
from .lasersourcedevice import LaserSourceDevice
from hardwarelibrary.capabilities import OnOffCapability, PowerCapability, InterlockCapability, AutostartCapability

import time
from threading import Thread, RLock

globalLock = RLock()


# Every Cobolt command is a line ending in \r, answered by a line ending in
# \r\n. The instrument acknowledges a setting with a bare "OK" and answers a
# query with the value alone, so the queries carry a field and the settings carry
# none. Nothing here says what turning the laser on does to a later reading, nor
# what it reads as when switched on: that is the laser, not its protocol, and it
# lives in DebugSerialPort below.
coboltProtocol = {
    "device": "Cobolt laser",
    "commands": {
        "GET_POWER": {
            "request": {"template": "pa?\r", "regex": r"pa\?\r"},
            "reply": {"regex": r"(\d+\.\d+)", "template": "{power:0.4f}\r\n",
                      "fields": {"power": "float"}},
        },
        "GET_REQUESTED_POWER": {
            "request": {"template": "p?\r", "regex": r"p\?\r"},
            "reply": {"regex": r"(\d+\.\d+)",
                      "template": "{requestedPower:0.4f}\r\n",
                      "fields": {"requestedPower": "float"}},
        },
        # "p" sets the power asked for, which "p?" reads back; "pa?" reads what
        # the laser has actually reached. Naming this field requestedPower rather
        # than power is what keeps those two apart.
        "SET_POWER": {
            "request": {"template": "p {requestedPower:0.3f}\r",
                        "regex": r"p ([0-9.]+)\r",
                        "fields": {"requestedPower": "float"}},
            "reply": {"regex": "OK", "template": "OK\r\n"},
        },
        "GET_ON_OFF": {
            "request": {"template": "l?\r", "regex": r"l\?\r"},
            "reply": {"regex": "(0|1)", "template": "{isOn:d}\r\n",
                      "fields": {"isOn": "boolean01"}},
        },
        "TURN_ON": {
            "request": {"template": "l1\r", "regex": r"l1\r"},
            "reply": {"regex": "OK", "template": "OK\r\n"},
        },
        "TURN_OFF": {
            "request": {"template": "l0\r", "regex": r"l0\r"},
            "reply": {"regex": "OK", "template": "OK\r\n"},
        },
        "GET_SERIAL_NUMBER": {
            "request": {"template": "sn?\r", "regex": r"sn\?\r"},
            "reply": {"regex": r"(\d+)", "template": "{serialNumber}\r\n",
                      "fields": {"serialNumber": "text"}},
        },
        "TURN_AUTOSTART_ON": {
            "request": {"template": "@cobas 1\r", "regex": r"@cobas 1\r"},
            "reply": {"regex": "OK", "template": "OK\r\n"},
        },
        "TURN_AUTOSTART_OFF": {
            "request": {"template": "@cobas 0\r", "regex": r"@cobas 0\r"},
            "reply": {"regex": "OK", "template": "OK\r\n"},
        },
        "GET_AUTOSTART": {
            "request": {"template": "@cobas?\r", "regex": r"@cobas\?\r"},
            "reply": {"regex": "(0|1)", "template": "{autostart:d}\r\n",
                      "fields": {"autostart": "boolean01"}},
        },
        "GET_INTERLOCK": {
            "request": {"template": "ilk?\r", "regex": r"ilk\?\r"},
            "reply": {"regex": "(0|1)", "template": "{interlock:d}\r\n",
                      "fields": {"interlock": "boolean01"}},
        },
    },
}

class CoboltCantTurnOnWithAutostartOn(Exception):
    pass

class CoboltDevice(LaserSourceDevice, OnOffCapability, PowerCapability,
                   InterlockCapability, AutostartCapability):
    protocol = CommandDictionary.fromDescription(coboltProtocol)

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

        super().__init__(serialNumber=serialNumber, idProduct=idProduct, idVendor=idVendor)
        self.port = None

    def __del__(self):
        try:
            self.port.close()
        except:
            # ignore if already closed
            return

    def canTurnOn(self) -> bool:
        return not self.doGetAutostart()

    def doInitializeDevice(self):
        try:
            if self.portPath == "debug":
                self.port = self.DebugSerialPort(self.protocol)
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
        self.interlockState = self.performTransaction("GET_INTERLOCK")["interlock"]
        return self.interlockState

    def doGetLaserSerialNumber(self) -> str:
        self.laserSerialNumber = self.performTransaction(
            "GET_SERIAL_NUMBER")["serialNumber"]

    def doGetOnOffState(self) -> bool:
        self.isOn = self.performTransaction("GET_ON_OFF")["isOn"]
        return self.isOn

    def doTurnOn(self):
        if not self.doGetAutostart():
            self.performTransaction("TURN_ON")
        else:
            raise CoboltCantTurnOnWithAutostartOn()

    def doTurnOff(self):
        self.performTransaction("TURN_OFF")

    def doGetAutostart(self) -> bool:
        self.autostart = self.performTransaction("GET_AUTOSTART")["autostart"]
        return self.autostart

    def doTurnAutostartOn(self):
        self.performTransaction("TURN_AUTOSTART_ON")
        self.autostart = True

    def doTurnAutostartOff(self):
        self.performTransaction("TURN_AUTOSTART_OFF")
        self.autostart = False

    def doSetPower(self, powerInWatts) -> float:
        self.performTransaction("SET_POWER", requestedPower=powerInWatts)
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
        return self.performTransaction("GET_POWER")["power"]

    class DebugSerialPort(ProtocolDebugPort):
        """A Cobolt without a Cobolt, mostly out of its own description.

        The wire, the initial readings and every setting that simply changes a
        later reading all come from coboltProtocol -- "sets" and "initial" carry
        those. What is left here is the one thing a description of a protocol has
        no business stating: a laser does not reach a new power instantly, so
        SET_POWER starts a ramp and GET_POWER reads whatever it has climbed to,
        which is what makes doSetPower's convergence loop mean something.
        """

        def __init__(self, protocol):
            """Start as a laser does when switched on, autostart engaged.

            Args:
                protocol: the CommandDictionary to answer from
            """
            super().__init__(protocol)
            self.values.update(power=0.1, requestedPower=0.0, isOn=False,
                               autostart=True, serialNumber="123456",
                               interlock=True)

        def answerFor(self, command) -> dict:
            """Act as the laser would, then answer as the description says.

            The store already holds whatever a request carried. What it cannot
            know is here: which readings a command changes without carrying them,
            and that a laser reaches a new power over about a second rather than
            at once -- which is what gives doSetPower's convergence loop
            something to converge to.

            Args:
                command: the command that was recognized

            Returns:
                The values its reply carries, taken from what is remembered.
            """
            with globalLock:
                if command.name == "TURN_ON":
                    self.values["isOn"] = True
                elif command.name == "TURN_OFF":
                    self.values["isOn"] = False
                elif command.name == "TURN_AUTOSTART_ON":
                    self.values["autostart"] = True
                elif command.name == "TURN_AUTOSTART_OFF":
                    self.values["autostart"] = False
                elif command.name == "SET_POWER":
                    Thread(target=increasePowerSlowlyInBackground,
                           kwargs=dict(port=self,
                                       endPower=self.values["requestedPower"],
                                       duration=1.0)).start()
                return super().answerFor(command)

        @property
        def power(self) -> float:
            """The power the laser has climbed to, for the ramp to move."""
            return self.values["power"]

        @power.setter
        def power(self, value: float):
            """Set the power the next GET_POWER will report."""
            self.values["power"] = value


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
