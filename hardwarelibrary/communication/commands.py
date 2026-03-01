"""Command classes that describe a device's communication protocol.

Each Command object serves two roles:

1. **Send side** (real device): build a payload, send it through a port,
   and parse the reply. This is done via the `send()` method.

2. **Recognition side** (mock/debug port): examine raw incoming bytes,
   decide if they match this command, extract parameters, and format
   a response. This is done via `matches()`, `extractParams()`, and
   `formatResponse()`.

By defining the protocol once in Command objects, the same definitions
drive both real communication and mock ports (TableDrivenDebugPort),
eliminating protocol duplication.

Subclasses:
    TextCommand    — text-based protocols (e.g. "s r0x24 31\\r" → "ok\\r")
    DataCommand    — binary protocols (e.g. struct-packed position commands)
    MultilineTextCommand — text protocols that return multiple lines
"""

import re
import struct

class Command:
    """Base class for all device commands.

    A Command has a name and tracks send/reply state. Subclasses override
    `send()` for the client side, and `matches()`/`extractParams()`/
    `formatResponse()` for the mock port side.

    Args:
        name: identifier for this command (e.g. "GET_POSITION", "SET_REGISTER")
        endPoints: tuple of (writeEndPoint, readEndPoint) for USB devices
                   that use separate endpoints for sending and receiving
    """

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

    @property
    def payload(self):
        return None

    @property
    def numberOfArguments(self):
        return 0

    def matchAsFloat(self, index=0):
        if self.matchGroups is not None:
            return float(self.matchGroups[index])
        return None

    @property
    def hasError(self):
        return len(self.exceptions) != 0

    def send(self, port) -> bool:
        """Send this command through a port. Subclasses must override."""
        raise NotImplementedError("Subclasses must implement the send() command")

    def matches(self, inputBytes):
        """Return True if inputBytes represents this command.
        Base implementation always returns False."""
        return False

    def extractParams(self, inputBytes):
        """Extract parameters from recognized input bytes.
        Returns a dict (named params) or tuple (positional params).
        Base implementation returns an empty tuple."""
        return ()

    def formatResponse(self, result):
        """Convert a process_command() return value into bytes for the output buffer.

        Args:
            result: the value returned by process_command():
                - None → returns None (no response sent)
                - bytes/bytearray → returned as-is
                - str → encoded to UTF-8
                - tuple or dict → handled by subclass (template/struct formatting)

        Returns:
            bytearray to write to the output buffer, or None.
        """
        if result is None:
            return None
        elif isinstance(result, (bytes, bytearray)):
            return bytearray(result)
        elif isinstance(result, str):
            return bytearray(result.encode('utf-8'))
        return None

class TextCommand(Command):
    """A command that communicates via text strings (UTF-8).

    Used for devices with text-based protocols like "s r0x24 31\\r" → "ok\\r".

    Send-side parameters (used by send()):
        text: format string sent to the device, e.g. "g r{register}\\n"
        replyPattern: regex to validate the device's reply
        alternatePattern: secondary regex if replyPattern doesn't match

    Recognition-side parameters (used by matches/extractParams/formatResponse):
        matchPattern: regex to recognize incoming bytes in a mock port.
                      Use named groups for readable code:
                      r'g r(?P<register>0x[0-9a-fA-F]+)[\\r\\n]'
                      If None, an auto-derived pattern from `text` is used.
        responseTemplate: format string for the mock response, e.g. "v {value}\\r".
                          Filled with named (dict) or positional (tuple) params
                          returned by process_command().

    Example:
        TextCommand(name="GET_REGISTER", text="g r{register}\\n",
                    matchPattern=r'g r(?P<register>0x[0-9a-fA-F]+)[\\r\\n]',
                    replyPattern=r'v\\s(-?\\d+)',
                    responseTemplate="v {value}\\r")
    """

    def __init__(self, name, text, replyPattern = None,
                                   alternatePattern = None,
                                   endPoints = (None, None),
                                   matchPattern = None,
                                   responseTemplate = None):
        Command.__init__(self, name, endPoints=endPoints)
        self.text : str = text
        self.replyPattern: str = replyPattern
        self.alternatePattern: str = alternatePattern
        self.matchPattern: str = matchPattern
        self.responseTemplate: str = responseTemplate

    @property
    def payload(self):
        return self.text

    @property
    def numberOfArguments(self):
        match = re.search(r"\{(.*?)\}", self.text)
        if match is None:
            return 0
        return len(match.groups())

    @property
    def _autoMatchPattern(self):
        """Derive a regex from the text format string by replacing {…}
        placeholders with (.+?) capture groups."""
        parts = re.split(r'\{[^}]*\}', self.text)
        escaped = [re.escape(p) for p in parts]
        return '(.+?)'.join(escaped)

    @property
    def effectiveMatchPattern(self):
        """Return the explicit matchPattern if set, otherwise the auto-derived one."""
        if self.matchPattern is not None:
            return self.matchPattern
        return self._autoMatchPattern

    def matches(self, inputBytes):
        """Return True if inputBytes matches this text command's pattern."""
        try:
            inputStr = inputBytes.decode('utf-8', errors='replace')
        except Exception:
            return False
        return re.match(self.effectiveMatchPattern, inputStr) is not None

    def extractParams(self, inputBytes):
        """Extract parameters from the input bytes using the match pattern.

        Returns a dict if the pattern uses named groups (?P<name>...),
        otherwise a tuple of positional groups."""
        try:
            inputStr = inputBytes.decode('utf-8', errors='replace')
        except Exception:
            return ()
        match = re.match(self.effectiveMatchPattern, inputStr)
        if match:
            if match.groupdict():
                return match.groupdict()
            return match.groups()
        return ()

    def formatResponse(self, result):
        """Format a mock response using the responseTemplate.

        - dict result → template.format(**result), e.g. {"value": "42"} → "v 42\\r"
        - tuple result → template.format(*result), e.g. ("42",) → "v 42\\r"
        - other types → delegated to base class (bytes/str as-is, None → None)
        """
        if isinstance(result, dict) and self.responseTemplate is not None:
            formatted = self.responseTemplate.format(**result)
            return bytearray(formatted.encode('utf-8'))
        if isinstance(result, tuple) and self.responseTemplate is not None:
            formatted = self.responseTemplate.format(*result)
            return bytearray(formatted.encode('utf-8'))
        return super().formatResponse(result)

    def send(self, port, params=None) -> bool:
        try:
            if params is not None:
                textCommand = self.text.format(params)
            else:
                textCommand = self.text

            if port is None:
                raise RuntimeError("port cannot be None")

            port.writeString(string=textCommand, endPoint=self.endPoints[0])
            self.isSent = True

            if self.replyPattern is not None:
                self.reply, self.matchGroups = port.readMatchingGroups(
                           replyPattern=self.replyPattern,
                           alternatePattern=self.alternatePattern,
                           endPoint=self.endPoints[1])
            else:
                pass
            
            self.isSentSuccessfully = True
        except Exception as err:
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            return True

        return False


class MultilineTextCommand(Command):
    """A text command that expects a multi-line reply.

    The reply is read either a fixed number of times (lineCount > 1) or
    until a line matches lastLinePattern. Each line is matched against
    replyPattern and the results are collected into lists.

    Args:
        lineCount: number of reply lines to read (if > 1)
        lastLinePattern: regex that signals the final line (alternative to lineCount)
    """

    def __init__(self, name, text,
                 replyPattern=None,
                 alternatePattern=None,
                 lineCount=1,
                 lastLinePattern=None,
                 endPoints=(None, None)):
        Command.__init__(self, name=name, endPoints=endPoints)
        self.text: str = text
        self.replyPattern: str = replyPattern
        self.alternatePattern: str = alternatePattern
        self.lineCount = lineCount
        self.lastLinePattern = lastLinePattern

    @property
    def payload(self):
        return self.text

    def send(self, port, params=None) -> bool:
        try:
            if params is not None:
                textCommand = self.text.format(params)
            else:
                textCommand = self.text

            if port is None:
                raise RuntimeError("port cannot be None")

            port.writeString(string=textCommand, endPoint=self.endPoints[0])
            self.isSent = True

            if self.lineCount > 1:
                self.reply = []
                self.matchGroups = []

                for i in range(self.lineCount):
                    reply, matchGroups = port.readMatchingGroups(
                        replyPattern=self.replyPattern,
                        alternatePattern=self.alternatePattern,
                        endPoint=self.endPoints[1])
                    self.reply.append(reply)
                    self.matchGroups.append(matchGroups)

            elif self.lastLinePattern is not None:
                self.reply = []
                self.matchGroups = []

                while True:
                    reply, matchGroups = port.readMatchingGroups(
                        replyPattern=self.replyPattern,
                        alternatePattern=self.alternatePattern,
                        endPoint=self.endPoints[1])
                    self.reply.append(reply)
                    self.matchGroups.append(matchGroups)

                    if re.search(self.lastLinePattern, reply) is not None:
                        break
            else:
                raise Exception("lineCount and lastLinePattern cannot both be None")

            self.isSentSuccessfully = True
        except Exception as err:
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            return True

        return False


class DataCommand(Command):
    """A command that communicates via binary data (struct-packed bytes).

    Used for devices with binary protocols like the Sutter micromanipulator
    where commands are single-byte prefixes followed by packed integers.

    Send-side parameters (used by send()):
        data: raw bytes to send to the device
        replyDataLength: number of bytes to read back
        unpackingMask: struct format to unpack the reply

    Recognition-side parameters (used by matches/extractParams/formatResponse):
        prefix: byte(s) that identify this command in incoming data.
                Matched case-insensitively. If None, derived from data[0:1].
        requestFormat: struct format to unpack incoming request parameters.
                       Padding bytes (x) are skipped automatically by struct.
        requestFields: tuple of field names for the unpacked values.
                       When set, extractParams() returns a dict:
                       e.g. requestFields=('x','y','z') → {'x': 10, 'y': 20, 'z': 30}
                       When None, extractParams() returns a positional tuple.
        responseFormat: struct format to pack the mock response.
        responseFields: tuple of field names expected in the response dict.
                        Defines the order for struct.pack when process_command()
                        returns a dict.

    Example:
        DataCommand(name="MOVE", prefix=b'M',
                    requestFormat='<xlllx', requestFields=('x', 'y', 'z'),
                    replyDataLength=1, unpackingMask='<c')

        DataCommand(name="GET_POSITION", prefix=b'C',
                    responseFormat='<clllc',
                    responseFields=('header', 'x', 'y', 'z', 'terminator'))
    """

    def __init__(self, name, data=None, replyHexRegex = None, replyDataLength = 0, unpackingMask = None, endPoints = (None, None),
                 prefix = None, requestFormat = None, responseFormat = None,
                 requestFields = None, responseFields = None):
        Command.__init__(self, name, endPoints=endPoints)
        self.data : bytearray = data
        self.replyHexRegex: str = replyHexRegex
        self.replyDataLength: int = replyDataLength
        self.unpackingMask:str = unpackingMask
        self._prefix: bytes = prefix
        self.requestFormat: str = requestFormat
        self.responseFormat: str = responseFormat
        self.requestFields: tuple = requestFields
        self.responseFields: tuple = responseFields

    @property
    def payload(self):
        return self.data

    @property
    def effectivePrefix(self):
        """Return the explicit prefix, or the first byte of data if not set."""
        if self._prefix is not None:
            return self._prefix
        if self.data is not None and len(self.data) > 0:
            return self.data[0:1]
        return None

    def matches(self, inputBytes):
        """Return True if inputBytes starts with this command's prefix (case-insensitive)."""
        prefix = self.effectivePrefix
        if prefix is None:
            return False
        prefixLen = len(prefix)
        if len(inputBytes) < prefixLen:
            return False
        return inputBytes[:prefixLen].upper() == prefix.upper()

    def extractParams(self, inputBytes):
        """Unpack parameters from the input bytes using requestFormat.

        Returns a dict if requestFields is set (e.g. {'x': 10, 'y': 20}),
        otherwise a positional tuple from struct.unpack."""
        if self.requestFormat is not None:
            unpackLen = struct.calcsize(self.requestFormat)
            if len(inputBytes) >= unpackLen:
                values = struct.unpack(self.requestFormat, bytes(inputBytes[:unpackLen]))
                if self.requestFields is not None:
                    return dict(zip(self.requestFields, values))
                return values
        return ()

    def formatResponse(self, result):
        """Pack a mock response using responseFormat.

        - dict result + responseFields → values ordered by responseFields, then packed
        - tuple result → packed directly with struct.pack
        - other types → delegated to base class (bytes/str as-is, None → None)
        """
        if isinstance(result, dict) and self.responseFormat is not None and self.responseFields is not None:
            values = tuple(result[f] for f in self.responseFields)
            data = struct.pack(self.responseFormat, *values)
            return bytearray(data)
        if isinstance(result, tuple) and self.responseFormat is not None:
            data = struct.pack(self.responseFormat, *result)
            return bytearray(data)
        return super().formatResponse(result)

    def send(self, port) -> bool:
        try:
            nBytes = port.writeData(data=self.data, endPoint=self.endPoints[0])
            self.isSent = True
            if self.replyDataLength > 0:
                self.reply = port.readData(length=self.replyDataLength)
            elif self.replyHexRegex is not None:
                raise NotImplementedError("DataCommand reply pattern not implemented")
                # self.reply = port.readData(length=self.replyDataLength)
            self.isSentSuccessfully = True
        except Exception as err:
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            raise(err)

        return False
