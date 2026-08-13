import time
import random
import struct
import re

from hardwarelibrary.communication import *
from threading import Thread, Lock

class DebugPort(CommunicationPort):
    def __init__(self, delay=0, numberOfEndPoints=1):
        self.inputBuffers = [bytearray() for _ in range(numberOfEndPoints)]
        self.outputBuffers = [bytearray() for _ in range(numberOfEndPoints)]
        self.delay = delay
        self.defaultTimeout = 500
        self._isOpen = False
        super(DebugPort, self).__init__()

    @property
    def isOpen(self):
        return self._isOpen

    def open(self):
        if self._isOpen:
            raise Exception("Port already open")

        self._isOpen = True

    def close(self):
        self._isOpen = False

    def bytesAvailable(self, endPoint=0):
        endPointIndex = endPoint if endPoint is not None else 0
        return len(self.outputBuffers[endPointIndex])

    def flush(self):
        for i in range(len(self.inputBuffers)):
            self.inputBuffers[i] = bytearray()
        for i in range(len(self.outputBuffers)):
            self.outputBuffers[i] = bytearray()

    def readData(self, length, endPoint=None):
        endPointIndex = 0 if endPoint is None else endPoint

        with self.portLock:
            if self.delay > 0:
                time.sleep(self.delay * random.random())

            data = bytearray()
            for i in range(length):
                if len(self.outputBuffers[endPointIndex]) > 0:
                    byte = self.outputBuffers[endPointIndex].pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read {0} bytes, only {1} available".format(length, len(data)))

        return data

    def writeData(self, data, endPoint=None):
        endPointIndex = 0 if endPoint is None else endPoint

        with self.portLock:
            self.inputBuffers[endPointIndex].extend(data)

        self.processInputBuffers(endPointIndex=endPointIndex)

        return len(data)

    def writeToOutputBuffer(self, data, endPointIndex=0):
        self.outputBuffers[endPointIndex].extend(data)

    def processInputBuffers(self, endPointIndex):
        # We default to ECHO for simplicity
        inputBytes = self.inputBuffers[endPointIndex]

        # Do something, here we do an Echo
        self.writeToOutputBuffer(inputBytes, endPointIndex)
        self.inputBuffers[endPointIndex] = bytearray()


class TableDrivenDebugPort(DebugPort):
    """A mock port that recognizes incoming commands and produces responses,
    driven by a dict of Command objects (TextCommand or DataCommand).

    Each Command object knows how to recognize itself in raw input bytes
    (matches/extractParams) and how to format a response (formatResponse).
    This means the same Command objects used by a real device to *send*
    commands can also be reused here to *recognize* them, eliminating
    protocol duplication between device code and mock code.

    To create a mock port for a device:

    1. Pass the device's commands dict to __init__:

        commands = {
            "GET": TextCommand(name="GET", text_format="GET {key}\\r",
                               matchPattern=r'GET (?P<key>\\w+)\\r',
                               responseTemplate="VAL {value}\\r"),
            "SET": DataCommand(name="SET", prefix=b'S',
                               requestFormat='<xl',
                               responseFormat='<cl'),
        }
        port = TableDrivenDebugPort(commands=commands)

    2. Override process_command() to implement device-specific logic:

        def process_command(self, name, params, endPointIndex):
            if name == "GET":
                key = params["key"]         # named group from matchPattern
                return {"value": self.values[key]}  # named param for responseTemplate
            elif name == "SET":
                self.value = params[0]      # positional from struct.unpack
                return b'\\x06'              # raw bytes returned as-is

    The name argument matches the Command's name. The params come from
    extractParams: a dict of named groups for TextCommand with (?P<name>...)
    patterns, a positional tuple for anonymous groups or struct.unpack.
    The return value is passed to formatResponse: dicts use named template
    parameters, tuples use positional parameters, raw bytes/strings are
    returned directly, None sends nothing.
    """

    def __init__(self, delay=0, numberOfEndPoints=1, commands=None):
        super().__init__(delay=delay, numberOfEndPoints=numberOfEndPoints)
        self.commands = commands if commands is not None else {}

    def processInputBuffers(self, endPointIndex):
        inputBytes = self.inputBuffers[endPointIndex]
        if len(inputBytes) == 0:
            return

        for cmd in self.commands.values():
            if cmd.matches(inputBytes):
                params = cmd.extractParams(inputBytes)
                result = self.process_command(cmd.name, params, endPointIndex)
                response = cmd.formatResponse(result)
                if response is not None:
                    self.writeToOutputBuffer(response, endPointIndex)
                self.inputBuffers[endPointIndex] = bytearray()
                return

        print("Unrecognized command: {0}".format(inputBytes))
        self.inputBuffers[endPointIndex] = bytearray()

    def process_command(self, name, params, endPointIndex):
        """Process a recognized command and return a result.

        Subclasses must override this to implement device behavior.

        Args:
            name: the Command's name (matches a key in self.commands)
            params: extracted parameters — a dict when using named regex
                    groups (?P<name>...), a tuple for anonymous groups or
                    struct.unpack fields
            endPointIndex: the endpoint the command arrived on

        Returns:
            The return value is passed to the command's formatResponse():
            - dict: formatted using named responseTemplate parameters
            - tuple: formatted using positional responseTemplate/responseFormat
            - bytes/str: written to the output buffer as-is
            - None: no response is sent
        """
        raise NotImplementedError("Subclasses must implement process_command")

class ProtocolDebugPort(DebugPort):
    """An instrument stood in for entirely by its own protocol description.

    Where TableDrivenDebugPort needs a subclass with a process_command full of
    branches, this needs nothing at all: hand it a CommandDictionary and it
    answers every command that dictionary describes. Two rules do the whole job,
    and both fall out of the fact that a command's two halves name their values
    the same way.

      - whatever a request carries is remembered, by name. MOVE arrives with x, y
        and z, so x, y and z are what the instrument now holds.
      - whatever a reply carries is answered from that memory. GET_POSITION asks
        for x, y and z, and gets back what MOVE left there.

    A value never set reads as 0, which is the state of an instrument that has
    just been switched on. A reply that cannot pack a 0 -- one carrying text, say
    -- will say so rather than invent something.

    The one thing no description of bytes can express is a command that changes
    the instrument without carrying anything: HOME takes no arguments and yet
    moves the stage to its origin. A command may therefore state a "sets" clause,
    which is applied on arrival exactly as a request's own values are. That
    clause is the only part of a description that talks about the instrument
    rather than the wire, and a driver never reads it.

    Recognising a request is the dictionary's work, not this class's: recognize()
    asks each command in turn, and the header constants settle it. So there is no
    second table of prefixes to keep in step with the driver.
    """

    def __init__(self, protocol, delay=0, numberOfEndPoints=1):
        """Stand in for the instrument a description describes.

        Args:
            protocol: the CommandDictionary to answer from
            delay: seconds of jitter to add to a read, as DebugPort applies it
            numberOfEndPoints: how many endpoints to pretend to have
        """
        super().__init__(delay=delay, numberOfEndPoints=numberOfEndPoints)
        self.protocol = protocol
        self.values = {}

    def processInputBuffers(self, endPointIndex):
        """Answer whatever complete request has arrived.

        Args:
            endPointIndex: which endpoint was written to

        Raises:
            RequestDidNotMatch: when the bytes are no command of this protocol,
                which means whatever wrote them is at fault -- a debug port that
                quietly dropped them would hide the bug it exists to find.
        """
        received = bytes(self.inputBuffers[endPointIndex])
        if len(received) == 0:
            return

        command, arguments = self.protocol.recognize(received)
        self.inputBuffers[endPointIndex] = bytearray()

        self.values.update(arguments)
        self.values.update(command.sets)
        if command.expectsReply:
            self.writeToOutputBuffer(command.encodeReply(**self.answerFor(command)),
                                     endPointIndex)

    def answerFor(self, command) -> dict:
        """The values to answer one command with, taken from what is remembered.

        Args:
            command: the command that was recognized

        Returns:
            {field name: value} for every value its reply carries, 0 for one that
            was never set. Empty for a reply that is nothing but a fixed
            acknowledgement, which the description supplies on its own.
        """
        return {name: self.values.get(name, 0)
                for name, _ in command.reply.parameters}
