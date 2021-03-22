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

class Command:
    def __init__(self, name:str):
        self.name = name
        self.reply = None

        self.matchGroups = None
        self.isSent = False
        self.isSentSuccessfully = False
        self.exceptions = []
        self.sendPortError = None
        self.replyPortError = None

        self.isReplyReceived = False
        self.isReplyReceivedSuccessfully = False

    def writeCommand(self, port):
        raise NotImplementedError()

    def readCommand(self, port):
        raise NotImplementedError()

class TextCommand(Command):
    def __init__(self, name, text, replyPattern = None, alternatePattern = None):
        Command.__init__(self, name)
        self.text : str = text
        self.replyPattern: str = replyPattern
        self.alternatePattern: str = alternatePattern

    def send(self, port) -> bool:
        try:
            if self.replyPattern is not None:
                self.reply, self.matchGroups = port.writeStringReadMatchingGroups(string=self.text,
                                                   replyPattern=self.replyPattern,
                                                   alternatePattern=self.alternatePattern)
            else:
                nBytes = port.writeString(string=self.text)
        except Exception as err:
            self.exceptions.append(err)
            print(err)
            return True

        return False


class DataCommand(Command):
    def __init__(self, name, data, replyHexRegex = None, replyLength = None, unpackingMask = None):
        Command.__init__(self, name)
        self.data : bytearray = None
        self.replyHexRegex: str = replyHexRegex
        self.replyDataLength: int = 0
        self.unpackingMask:str = unpackingMask

    def writeCommand(self, port):
        if self.replyDataLength != 0:
            nBytes = port.writeData(self.data)

            self.reply = self.port.readData(self.replyDataLength)

    def readCommand(self, port):
        raise NotImplementedError()

class CommunicationPort:
    """CommunicationPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.

    """
    
    def __init__(self):
        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        raise NotImplementedError()

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def bytesAvailable(self) -> int:
        raise NotImplementedError()

    def flush(self):
        raise NotImplementedError()

    def readData(self, length, endpoint=0) -> bytearray:
        raise NotImplementedError()

    def writeData(self, data, endpoint=0) -> int:
        raise NotImplementedError()

    def readString(self, endpoint=0) -> str:      
        with self.portLock:
            byte = None
            data = bytearray(0)
            while (byte != b''):
                byte = self.readData(1, endpoint)
                data += byte
                if byte == b'\n':
                    break

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string, endpoint=0) -> int:
        nBytes = 0
        with self.portLock:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data, endpoint)

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern, alternatePattern = None, endPoints=(0,0)):
        with self.transactionLock:
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])
            match = re.search(replyPattern, reply)
            if match is None:
                if alternatePattern is not None:
                    match = re.search(alternatePattern, reply)
                    if match is None:
                        raise CommunicationReadAlternateMatch(reply)
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}'".format(replyPattern))

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern, alternatePattern = None, endPoints=(0,0)):
        with self.transactionLock:
            reply, groups = self.writeStringReadMatchingGroups(string, replyPattern, alternatePattern, endPoints)
            if len(groups) >= 1:
                return reply, groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}' in {1}".format(replyPattern, groups))

    def writeStringReadMatchingGroups(self, string, replyPattern, alternatePattern = None, endPoints=(0,0)):
        with self.transactionLock:
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])

            match = re.search(replyPattern, reply)

            if match is not None:
                return reply, match.groups()
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))


class DebugEchoCommunicationPort(CommunicationPort):
    def __init__(self, delay=0):
        self.buffer = bytearray()
        self.delay = delay
        self._isOpen = False
        super(DebugEchoCommunicationPort, self).__init__()

    @property
    def isOpen(self):
        return self._isOpen    

    def open(self):
        if self._isOpen:
            raise Exception()

        self._isOpen = True
        return

    def close(self):
        self._isOpen = False
        return

    def bytesAvailable(self):
        return len(self.buffer)

    def flush(self):
        self.buffer = bytearray()

    def readData(self, length, endpoint=0):
        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.buffer) > 0:
                    byte = self.buffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data, endpoint=0):
        with self.portLock:
            self.buffer.extend(data)

        return len(data)
