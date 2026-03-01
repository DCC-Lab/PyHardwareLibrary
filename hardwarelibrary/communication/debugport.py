import time
import random
import struct
import re
from dataclasses import dataclass

from hardwarelibrary.communication import *
from threading import Thread, Lock


@dataclass
class BinaryCommandEntry:
    name: str
    prefix: bytes
    request_format: str = None
    request_length: int = None
    response_format: str = None


@dataclass
class TextCommandEntry:
    name: str
    pattern: str
    response: str = None

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
        endPointIndex = endPoint if endPoint is not None else 0

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
        endPointIndex = endPoint if endPoint is not None else 0

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
    def __init__(self, delay=0, numberOfEndPoints=1):
        super().__init__(delay=delay, numberOfEndPoints=numberOfEndPoints)
        self.binary_commands = []
        self.text_commands = []

    def processInputBuffers(self, endPointIndex):
        inputBytes = self.inputBuffers[endPointIndex]
        if len(inputBytes) == 0:
            return

        for cmd in self.binary_commands:
            prefix_len = len(cmd.prefix)
            if inputBytes[:prefix_len].upper() == cmd.prefix.upper():
                if cmd.request_format is not None:
                    unpack_len = struct.calcsize(cmd.request_format)
                    params = struct.unpack(cmd.request_format, bytes(inputBytes[:unpack_len]))
                else:
                    params = ()

                result = self.process_command(cmd.name, params, endPointIndex)
                self._write_binary_response(result, cmd, endPointIndex)
                self.inputBuffers[endPointIndex] = bytearray()
                return

        inputStr = inputBytes.decode('utf-8', errors='replace')
        for cmd in self.text_commands:
            match = re.match(cmd.pattern, inputStr)
            if match:
                params = match.groups()
                result = self.process_command(cmd.name, params, endPointIndex)
                self._write_text_response(result, cmd, endPointIndex)
                self.inputBuffers[endPointIndex] = bytearray()
                return

        print("Unrecognized command: {0}".format(inputBytes))
        self.inputBuffers[endPointIndex] = bytearray()

    def _write_binary_response(self, result, cmd, endPointIndex):
        if result is None:
            return
        elif isinstance(result, (bytes, bytearray)):
            self.writeToOutputBuffer(bytearray(result), endPointIndex)
        elif isinstance(result, str):
            self.writeToOutputBuffer(bytearray(result.encode('utf-8')), endPointIndex)
        elif isinstance(result, tuple) and cmd.response_format is not None:
            data = struct.pack(cmd.response_format, *result)
            self.writeToOutputBuffer(bytearray(data), endPointIndex)

    def _write_text_response(self, result, cmd, endPointIndex):
        if result is None:
            return
        elif isinstance(result, (bytes, bytearray)):
            self.writeToOutputBuffer(bytearray(result), endPointIndex)
        elif isinstance(result, str):
            self.writeToOutputBuffer(bytearray(result.encode('utf-8')), endPointIndex)
        elif isinstance(result, tuple) and cmd.response is not None:
            formatted = cmd.response.format(*result)
            self.writeToOutputBuffer(bytearray(formatted.encode('utf-8')), endPointIndex)

    def process_command(self, name, params, endPointIndex):
        raise NotImplementedError("Subclasses must implement process_command")