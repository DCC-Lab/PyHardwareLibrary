import serial
import re
import time
import random
import inspect
from threading import RLock
from .commands import *

class CommunicationReadTimeout(serial.SerialException):
    pass

class CommunicationReadNoMatch(Exception):
    pass

class CommunicationReadError(Exception):
    """The reply did not match replyPattern but matched the caller's
    errorPattern: a recognized error/exceptional reply from the device,
    as opposed to CommunicationReadNoMatch which means the reply was
    unintelligible (likely a framing desync). Carries the errorPattern
    capture groups so the caller can extract the error code/message without
    re-matching."""
    def __init__(self, reply, groups):
        self.reply = reply
        self.groups = groups
        super().__init__(reply)

# Deprecated alias for CommunicationReadError, kept for backward compatibility.
# It will be removed in a future release; use CommunicationReadError instead.
CommunicationReadAlternateMatch = CommunicationReadError

class CommunicationPort:
    """CommunicationPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.

    """
    
    def __init__(self):
        self.portLock = RLock()
        self.transactionLock = RLock()
        self.terminator = b'\n'

    @property
    def isOpen(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    @property
    def isNotOpen(self):
        return not self.isOpen

    def open(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def close(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def bytesAvailable(self) -> int:
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def flush(self):
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def readData(self, length, endPoint=None) -> bytearray:
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def writeData(self, data, endPoint=None) -> int:
        fctName = inspect.currentframe().f_code.co_name
        raise NotImplementedError("Derived class must implement {0}".format(fctName))

    def readString(self, endPoint=None) -> str:      
        with self.portLock:
            byte = None
            data = bytearray(0)
            try:
                while (byte != b''):
                    byte = self.readData(1, endPoint)
                    data += byte
                    if byte == self.terminator:
                        break
            except CommunicationReadTimeout as err:
                raise CommunicationReadTimeout("Only obtained {0}".format(data))

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string, endPoint=None) -> int:
        nBytes = 0
        with self.portLock:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data, endPoint)

        return nBytes

    # The next five methods are the write-then-read(-then-match) transaction a
    # driver's own query method should delegate to, not reimplement. A driver
    # that instead hand-rolls `writeString(...)` + `readString()` +
    # `re.search(pattern, reply).group(...)` loses transactionLock-protected
    # atomicity for free, and gets a bare AttributeError on a mismatched reply
    # instead of the CommunicationReadNoMatch these raise. `flushFirst=True` is
    # the one instrument-specific quirk this family covers by itself: a
    # protocol that leaves unread bytes behind after every reply (the next
    # read would otherwise return the previous reply's leftovers) needs the
    # port flushed before each write (see MillenniaEv25Device.queryString,
    # FianiumLaserDevice.queryString/queryMatchingGroups -- each a one-line
    # delegation, not a custom wrapper). flushFirst is False by default
    # because flushing is not free of risk for every protocol: a multi-line
    # reply still being drained would have its remainder discarded. Write a
    # wrapper around one of these only for a quirk flushFirst does not cover;
    # before adding one, check whether an existing driver already solved the
    # same shape of transaction.
    def writeStringExpectMatchingString(self, string, replyPattern, errorPattern = None, endPoints=(None,None), flushFirst=False):
        reply, _ = self.writeStringReadMatch(string, replyPattern, errorPattern, endPoints, flushFirst)
        return reply

    def writeStringReadMatchingGroups(self, string, replyPattern, errorPattern = None, endPoints=(None,None), flushFirst=False):
        reply, match = self.writeStringReadMatch(string, replyPattern, errorPattern, endPoints, flushFirst)
        return reply, match.groups()

    def writeStringReadFirstMatchingGroup(self, string, replyPattern, errorPattern = None, endPoints=(None,None), flushFirst=False):
        reply, groups = self.writeStringReadMatchingGroups(string, replyPattern, errorPattern, endPoints, flushFirst)
        if len(groups) >= 1:
            return reply, groups[0]
        else:
            raise CommunicationReadNoMatch("Pattern '{0}' matched but captured no group in reply:'{1}'".format(replyPattern, reply))

    def writeStringReadMatch(self, string, replyPattern, errorPattern = None, endPoints=(None,None), flushFirst=False):
        # The single write-then-read-then-match transaction the three
        # writeString* methods above share.
        with self.transactionLock:
            if flushFirst:
                self.flush()
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])
            return reply, self.matchReply(reply, replyPattern, errorPattern)

    def writeStringReadReply(self, string, endPoints=(None,None), flushFirst=False) -> str:
        """Write string and return the reply, with no pattern to match against.

        For a driver's free-form status queries (alarms, mode, ...) that have
        no fixed reply format worth validating -- see writeStringReadMatch's
        family above for a reply with a known structure instead.
        """
        with self.transactionLock:
            if flushFirst:
                self.flush()
            self.writeString(string, endPoints[0])
            return self.readString(endPoints[1])

    def readMatchingGroups(self, replyPattern, errorPattern = None, endPoint=None):
        reply = self.readString(endPoint=endPoint)
        return reply, self.matchReply(reply, replyPattern, errorPattern).groups()

    def matchReply(self, reply, replyPattern, errorPattern = None):
        # replyPattern is the success reply; errorPattern is a recognized error
        # reply that raises CommunicationReadAlternateMatch carrying its capture
        # groups; a reply matching neither raises CommunicationReadNoMatch.
        match = re.search(replyPattern, reply)
        if match is not None:
            return match

        if errorPattern is not None:
            error = re.search(errorPattern, reply)
            if error is not None:
                raise CommunicationReadError(reply, error.groups())

        raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))

