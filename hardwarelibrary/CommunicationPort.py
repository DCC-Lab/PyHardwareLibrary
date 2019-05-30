import serial
import re
import time
import random
from threading import Thread, RLock

class CommunicationReadTimeout(serial.SerialException):
    pass

class CommunicationReadNoMatch(Exception):
    pass

class CommunicationReadAlternateMatch(Exception):
    pass

class CommunicationPort:
    """CommunicationPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.

    Two strategies to initialize the CommunicationPort:
    1. with a bsdPath/port name (i.e. "COM1" or "/dev/cu.serial")
    2. with an instance of SerialPort() that will support the same
       functions as pyserial.Serial() (open, close, read, write, readline)
    """
    
    def __init__(self, bsdPath=None, portPath=None, port = None):
        if bsdPath is not None:
            self.portPath = bsdPath
        elif portPath is not None:
            self.portPath = portPath
        else:
            self.portPath = None

        if port is not None and port.is_open:
            port.close()
        self.port = port # direct port, must be closed.

        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        if self.port is None:
            return False    
        else:
            return self.port.is_open    

    def open(self):
        if self.port is None:
            self.port = serial.Serial(self.portPath, 19200, timeout=0.3)
        else:
            self.port.open()

    def close(self):
        self.port.close()

    def bytesAvailable(self) -> int:
        return self.port.in_waiting

    def flush(self):
        if self.isOpen:
            self.port.reset_input_buffer()
            self.port.reset_output_buffer()

    def readData(self, length) -> bytearray:
        with self.portLock:
            data = self.port.read(length)
            if len(data) != length:
                raise CommunicationReadTimeout()

        return data

    def writeData(self, data) -> int:
        with self.portLock:
            nBytesWritten = self.port.write(data)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")
            self.port.flush()

        return nBytesWritten

    def readString(self) -> str:      
        with self.portLock:
            byte = None
            data = bytearray(0)
            while (byte != b''):
                byte = self.readData(1)
                data += byte
                if byte == b'\n':
                    break

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string) -> int:
        nBytes = 0
        with self.portLock:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data)

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern, alternatePattern = None):
        with self.transactionLock:
            self.writeString(string)
            reply = self.readString()
            match = re.search(replyPattern, reply)
            if match is None:
                if alternatePattern is not None:
                    match = re.search(alternatePattern, reply)
                    if match is None:
                        raise CommunicationReadAlternateMatch(reply)
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}'".format(replyPattern))

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern, alternatePattern = None):
        with self.transactionLock:
            groups = self.writeStringReadMatchingGroups(string, replyPattern, alternatePattern)
            if len(groups) >= 1:
                return groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}' in {1}".format(replyPattern, groups))

    def writeStringReadMatchingGroups(self, string, replyPattern, alternatePattern = None):
        with self.transactionLock:
            self.writeString(string)
            reply = self.readString()

            match = re.search(replyPattern, reply)

            if match is not None:
                return match.groups()
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))


class CommandString:
    def __init__(self, name, pattern):
        self.text = ""
        self.name = name
        self.pattern = pattern
        self.groups = ()

    def match(self, inputData) -> re.Match:
        inputString = inputData.decode('utf-8')
        return re.search(self.pattern, inputString)

class CommandData:
    def __init__(self, name, hexPattern, dataLength):
        self.data = bytearray()
        self.name = name
        self.hexPattern = hexPattern
        self.dataLength = dataLength
        self.groups = ()

    def match(self, inputData) -> re.Match:
        inputHexString = inputData.hex()
        return re.search(self.hexPattern, inputHexString)

class DebugCommunicationPort(CommunicationPort):
    def __init__(self, isBinary=False, delay=0):
        self.isBinary = isBinary
        self.delay = delay
        self.lineEnding = b'\r'
        self.lock = RLock()

        self.outputBuffer = bytearray()
        self.commands = []
        self._isOpen = False
        super(DebugCommunicationPort, self).__init__()
    
    @property
    def isOpen(self):
        return self._isOpen    
    
    def open(self):
        with self.lock:
            if self._isOpen:
                raise IOError("port is already open")
            else:
                self._isOpen = True
        return

    def close(self):
        with self.lock:
            self._isOpen = False

        return

    def flush(self):
        return

    def readData(self, length) -> bytearray:
        with self.lock:
            data = bytearray()
            for i in range(0, length):
                if len(self.outputBuffer) > 0:
                    byte = self.outputBuffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data


    def writeData(self, data:bytearray) -> int :
        with self.lock:
            for command in self.commands:
                match = command.match(data) 
                if match is not None:      
                    if command is isinstance(command, CommandData):            
                        replyData = self.processCommand(command, match.groups(), data)
                    else:
                        replyString = self.processCommand(command, match.groups(), data.decode('utf-8') )
                        replyData = replyString.encode()

                    self.outputBuffer.extend(replyData)

                    break

            return len(replyData)

class DebugEchoCommunicationPort(DebugCommunicationPort):
    def __init__(self, delay=0):
        super(DebugEchoCommunicationPort, self).__init__(delay=delay)
        self.commands.append(CommandString(name='echo', pattern='(.)+'))

    def processCommand(self, command, groups, inputString) -> bytearray:
        if command.name == 'echo':
            return inputString

        raise CommunicationPortUnrecognizedCommand("Unrecognized command: {0}".format(inputString))
