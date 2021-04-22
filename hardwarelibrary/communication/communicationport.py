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
    def __init__(self, name:str, endPoints = (None, None)):
        self.name = name
        self.reply = None
        self.matchGroups = None
        self.endPoints = endPoints

        self.isSent = False
        self.isSentSuccessfully = False
        self.exceptions = []

        self.isReplyReceived = False
        self.isReplyReceivedSuccessfully = False

    def matchAsFloat(self, index=0):
        if self.matchGroups is not None:
            return float(self.matchGroups[index])
        return None
    
    @property
    def hasError(self):
        return len(self.exceptions) != 0

    def send(self, port) -> bool:
        raise NotImplementedError()

class TextCommand(Command):
    def __init__(self, name, text, replyPattern = None, alternatePattern = None, endPoints = (None, None)):
        Command.__init__(self, name, endPoints=endPoints)
        self.text : str = text
        self.replyPattern: str = replyPattern
        self.alternatePattern: str = alternatePattern

    def send(self, port, params=None) -> bool:
        try:
            self.isSent = True
            if params is not None:
                textCommand = self.text.format(params)
            else:
                textCommand = self.text

            if self.replyPattern is not None:
                self.reply, self.matchGroups = port.writeStringReadMatchingGroups(string=textCommand,
                                                   replyPattern=self.replyPattern,
                                                   alternatePattern=self.alternatePattern,
                                                   endPoints=self.endPoints)
            else:
                nBytes = port.writeString(string=textCommand, endPoint=self.endPoints[0])
            self.isSentSuccessfully = True
        except Exception as err:
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            return True

        return False


class DataCommand(Command):
    def __init__(self, name, data, replyHexRegex = None, replyDataLength = 0, unpackingMask = None, endPoints = None):
        Command.__init__(self, name, endPoints=endPoints)
        self.data : bytearray = data
        self.replyHexRegex: str = replyHexRegex
        self.replyDataLength: int = replyDataLength
        self.unpackingMask:str = unpackingMask

    def send(self, port) -> bool:
        try:
            self.isSent = True
            nBytes = port.writeData(data=self.data, endPoint=self.endPoints[0])
            if self.replyDataLength > 0:
                self.reply = port.readData(length=self.replyDataLength)
            elif self.replyHexRegex is not None:
                raise NotImplementedError()
                # self.reply = port.readData(length=self.replyDataLength)
            self.isSentSuccessfully = True
        except Exception as err:
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            return True

        return False

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

    def readData(self, length, endPoint=None) -> bytearray:
        raise NotImplementedError()

    def writeData(self, data, endPoint=None) -> int:
        raise NotImplementedError()

    def readString(self, endPoint=None) -> str:      
        with self.portLock:
            byte = None
            data = bytearray(0)
            while (byte != b''):
                byte = self.readData(1, endPoint)
                data += byte
                if byte == b'\n':
                    break

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string, endPoint=None) -> int:
        nBytes = 0
        with self.portLock:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data, endPoint)

        return nBytes

    def writeStringExpectMatchingString(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
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

    def writeStringReadFirstMatchingGroup(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
        with self.transactionLock:
            reply, groups = self.writeStringReadMatchingGroups(string, replyPattern, alternatePattern, endPoints)
            if len(groups) >= 1:
                return reply, groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}' in {1}".format(replyPattern, groups))

    def writeStringReadMatchingGroups(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
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
        self.buffers = [bytearray(),bytearray()]
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

    def bytesAvailable(self, endPoint=0):
        return len(self.buffers[endPoint])

    def flush(self):
        self.buffers = [bytearray(),bytearray()]

    def readData(self, length, endPoint=0):
        with self.portLock:
            time.sleep(self.delay*random.random())
            data = bytearray()
            for i in range(0, length):
                if len(self.buffers[endPoint]) > 0:
                    byte = self.buffers[endPoint].pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data

    def writeData(self, data, endPoint=0):
        with self.portLock:
            self.buffers[endPoint].extend(data)

        return len(data)
