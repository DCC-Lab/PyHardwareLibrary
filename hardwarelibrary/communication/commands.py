"""Command classes that describe a device's communication protocol.

Every PhysicalDevice can define a ``commands`` dictionary -- a dict of
Command objects that fully describes its protocol. For example, a Sutter
micromanipulator defines MOVE, GET_POSITION, and HOME commands, while an
Intellidrive rotation stage defines SET_REGISTER, GET_REGISTER, and
TRAJECTORY commands.

This dictionary is useful in two complementary ways:

1. **Talking to a real device**: each Command knows how to build a
   payload, send it through a port, and parse the reply. The device
   code calls ``send()`` and reads back ``reply`` / ``matchGroups``.

2. **Creating a mock debug port**: the same Command objects can be
   passed to a ``TableDrivenDebugPort``, which reverses the roles --
   it *receives* those commands instead of sending them, extracts the
   parameters from the incoming bytes, and replies in the correct
   format.

Every Command has four conceptual operations, named consistently across
``TextCommand`` and ``DataCommand``:

    requestEncoder   encode an outgoing request payload   (device -> wire)
    requestDecoder   decode an incoming request payload   (wire -> mock)
    replyEncoder     encode an outgoing reply payload     (mock -> wire)
    replyDecoder     decode an incoming reply payload     (wire -> device)

For ``TextCommand`` each is a string -- a Python format string for the
encoders, a regex for the decoders.

For ``DataCommand`` each is a small dataclass (``DataEncoder`` /
``DataDecoder``) that bundles a struct format with its field names.
"""

import re
import struct
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DataEncoder:
    """Schema for serializing structured params into bytes (DataCommand).

    Attributes:
        format:   struct format string, e.g. '<clllc'
        fields:   field names paired with the format, e.g. ('x', 'y', 'z')
        defaults: values for fields not supplied at call time, e.g. {'header': b'M'}
    """
    format: str
    fields: tuple = ()
    defaults: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DataDecoder:
    """Schema for parsing bytes into structured params (DataCommand).

    Attributes:
        format: struct format string. May be '' when only a prefix is meaningful.
        fields: field names paired with the format. Empty tuple => positional tuple unpack.
        length: bytes to read from the port. Used by replyDecoder; ignored by requestDecoder.
        prefix: leading bytes that identify the command for mock dispatch.
                Used by requestDecoder; ignored by replyDecoder.
    """
    format: str = ''
    fields: tuple = ()
    length: int = 0
    prefix: Optional[bytes] = None


class Command:
    """Base class for all device commands.

    A Command has a name and tracks per-call state (reply, matchGroups,
    exceptions). Subclasses override ``send()`` for the client side and
    ``matches()``/``extractParams()``/``formatResponse()`` for the mock
    port side.

    Args:
        name:     identifier (key in the device's ``commands`` dict)
        endPoints: tuple of (writeEndPoint, readEndPoint) for USB
                   devices that use distinct endpoints
    """

    def __init__(self, name: str, endPoints=(None, None)):
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
        raise NotImplementedError("Subclasses must implement send()")

    def matches(self, inputBytes):
        return False

    def extractParams(self, inputBytes):
        return ()

    def formatResponse(self, result):
        """Convert a process_command() return value into bytes for the output buffer.

        Handles the common cases (None / bytes / str). Subclasses extend
        for typed encoding (dict + responseTemplate, dict + responseFormat).
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

    Each of the four operations is a string -- a format string for encoders,
    a regex for decoders.

    Attributes:
        requestEncoder: format string for the outgoing request,
                        e.g. "g r{register}\\n"
        requestDecoder: regex with named groups for the mock to recognize
                        an incoming request, e.g.
                        r'g r(?P<register>0x[0-9a-fA-F]+)[\\r\\n]'.
                        If None, derived from requestEncoder by replacing
                        each {...} placeholder with (.+?).
        replyDecoder:   regex to parse the device's reply,
                        e.g. r'v\\s(-?\\d+)'.
        replyEncoder:   format string for the mock's reply,
                        e.g. "v {value}\\r".

    Example:
        TextCommand(
            name="GET_REGISTER",
            requestEncoder="g r{register}\\n",
            requestDecoder=r'g r(?P<register>0x[0-9a-fA-F]+)[\\r\\n]',
            replyDecoder=r'v\\s(-?\\d+)',
            replyEncoder="v {value}\\r",
        )
    """

    def __init__(self, name,
                 requestEncoder=None,
                 requestDecoder=None,
                 replyDecoder=None,
                 replyEncoder=None,
                 endPoints=(None, None)):
        Command.__init__(self, name, endPoints=endPoints)
        self.requestEncoder = requestEncoder
        self.requestDecoder = requestDecoder
        self.replyDecoder = replyDecoder
        self.replyEncoder = replyEncoder

    @property
    def payload(self):
        return self.requestEncoder

    @property
    def numberOfArguments(self):
        if self.requestEncoder is None:
            return 0
        match = re.search(r"\{(.*?)\}", self.requestEncoder)
        if match is None:
            return 0
        return len(match.groups())

    def _autoMatchPattern(self):
        """Derive a regex from requestEncoder by escaping it and replacing
        every {...} placeholder with a (.+?) capture group."""
        if self.requestEncoder is None:
            return None
        parts = re.split(r'\{[^}]*\}', self.requestEncoder)
        escaped = [re.escape(p) for p in parts]
        return '(.+?)'.join(escaped)

    @property
    def effectiveDecoder(self):
        """The regex used by matches/extractParams: requestDecoder if set,
        otherwise the auto-derived pattern from requestEncoder."""
        if self.requestDecoder is not None:
            return self.requestDecoder
        return self._autoMatchPattern()

    def matches(self, inputBytes):
        pattern = self.effectiveDecoder
        if pattern is None:
            return False
        try:
            inputStr = inputBytes.decode('utf-8', errors='replace')
        except Exception:
            return False
        return re.match(pattern, inputStr) is not None

    def extractParams(self, inputBytes):
        """Extract params from inputBytes using effectiveDecoder.

        Returns a dict if the pattern uses named groups (?P<name>...),
        otherwise a tuple of positional capture groups.
        """
        pattern = self.effectiveDecoder
        if pattern is None:
            return ()
        try:
            inputStr = inputBytes.decode('utf-8', errors='replace')
        except Exception:
            return ()
        match = re.match(pattern, inputStr)
        if match:
            if match.groupdict():
                return match.groupdict()
            return match.groups()
        return ()

    def formatResponse(self, result):
        """Format a mock response using replyEncoder.

        - dict result + replyEncoder  -> replyEncoder.format(**result)
        - tuple result + replyEncoder -> replyEncoder.format(*result)
        - other types                 -> delegated to base (bytes/str/None)
        """
        if isinstance(result, dict) and self.replyEncoder is not None:
            formatted = self.replyEncoder.format(**result)
            return bytearray(formatted.encode('utf-8'))
        if isinstance(result, tuple) and self.replyEncoder is not None:
            formatted = self.replyEncoder.format(*result)
            return bytearray(formatted.encode('utf-8'))
        return super().formatResponse(result)

    def send(self, port, params=None) -> bool:
        try:
            if params is not None:
                textCommand = self.requestEncoder.format(params)
            else:
                textCommand = self.requestEncoder

            if port is None:
                raise RuntimeError("port cannot be None")

            port.writeString(string=textCommand, endPoint=self.endPoints[0])
            self.isSent = True

            if self.replyDecoder is not None:
                self.reply, self.matchGroups = port.readMatchingGroups(
                    replyPattern=self.replyDecoder,
                    endPoint=self.endPoints[1])

            self.isSentSuccessfully = True
        except Exception as err:
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            return True

        return False


class MultilineTextCommand(Command):
    """A TextCommand variant whose reply spans multiple lines.

    The reply is read either a fixed number of times (lineCount > 1) or
    until a line matches lastLinePattern. Each line is matched against
    replyDecoder; the collected results land in self.reply / self.matchGroups
    as lists.

    Attributes:
        requestEncoder:  format string for the outgoing request
        replyDecoder:    regex to parse each reply line
        lineCount:       number of reply lines to read (if > 1)
        lastLinePattern: regex that signals the final line (alternative to lineCount)
    """

    def __init__(self, name,
                 requestEncoder=None,
                 replyDecoder=None,
                 lineCount=1,
                 lastLinePattern=None,
                 endPoints=(None, None)):
        Command.__init__(self, name=name, endPoints=endPoints)
        self.requestEncoder = requestEncoder
        self.replyDecoder = replyDecoder
        self.lineCount = lineCount
        self.lastLinePattern = lastLinePattern

    @property
    def payload(self):
        return self.requestEncoder

    def send(self, port, params=None) -> bool:
        try:
            if params is not None:
                textCommand = self.requestEncoder.format(params)
            else:
                textCommand = self.requestEncoder

            if port is None:
                raise RuntimeError("port cannot be None")

            port.writeString(string=textCommand, endPoint=self.endPoints[0])
            self.isSent = True

            if self.lineCount > 1:
                self.reply = []
                self.matchGroups = []
                for i in range(self.lineCount):
                    reply, matchGroups = port.readMatchingGroups(
                        replyPattern=self.replyDecoder,
                        endPoint=self.endPoints[1])
                    self.reply.append(reply)
                    self.matchGroups.append(matchGroups)
            elif self.lastLinePattern is not None:
                self.reply = []
                self.matchGroups = []
                while True:
                    reply, matchGroups = port.readMatchingGroups(
                        replyPattern=self.replyDecoder,
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
    """A command that communicates via binary struct-packed bytes.

    Used for devices with binary protocols like the Sutter MP-285 where
    commands are single-byte prefixes followed by packed integers.

    Attributes:
        requestEncoder: DataEncoder for the outgoing request bytes
        requestDecoder: DataDecoder used by a mock to parse the incoming request
        replyDecoder:   DataDecoder used by the device to parse the reply
                        (its ``length`` field tells how many bytes to read)
        replyEncoder:   DataEncoder used by a mock to pack its reply
        data:           precomputed request bytes. Used when requestEncoder is
                        None (e.g. fixed commands with no parameters), and also
                        provides a prefix fallback: ``data[0:1]`` is the
                        command prefix when ``requestDecoder.prefix`` is unset.

    Example:
        DataCommand(
            name="MOVE",
            requestEncoder=DataEncoder('<clllc',
                                       ('header','x','y','z','terminator'),
                                       {'header': b'M', 'terminator': b'\\r'}),
            requestDecoder=DataDecoder('<xlllx', ('x','y','z'), prefix=b'M'),
            replyDecoder=DataDecoder('<c', length=1),
        )
    """

    def __init__(self, name,
                 requestEncoder=None,
                 requestDecoder=None,
                 replyDecoder=None,
                 replyEncoder=None,
                 data=None,
                 endPoints=(None, None)):
        Command.__init__(self, name, endPoints=endPoints)
        self.requestEncoder = requestEncoder
        self.requestDecoder = requestDecoder
        self.replyDecoder = replyDecoder
        self.replyEncoder = replyEncoder
        self.data = data

    @property
    def payload(self):
        return self.data

    @property
    def effectivePrefix(self):
        """Prefix used by matches(): requestDecoder.prefix if set,
        otherwise data[0:1] as a fallback."""
        if self.requestDecoder is not None and self.requestDecoder.prefix is not None:
            return self.requestDecoder.prefix
        if self.data is not None and len(self.data) > 0:
            return self.data[0:1]
        return None

    def matches(self, inputBytes):
        prefix = self.effectivePrefix
        if prefix is None:
            return False
        prefixLen = len(prefix)
        if len(inputBytes) < prefixLen:
            return False
        return inputBytes[:prefixLen].upper() == prefix.upper()

    def extractParams(self, inputBytes):
        """Unpack params from inputBytes via requestDecoder.

        Returns a dict if requestDecoder.fields is set (named unpack),
        otherwise a positional tuple from struct.unpack.
        """
        if self.requestDecoder is None:
            return ()
        fmt = self.requestDecoder.format
        if not fmt:
            return ()
        unpackLen = struct.calcsize(fmt)
        if len(inputBytes) < unpackLen:
            return ()
        values = struct.unpack(fmt, bytes(inputBytes[:unpackLen]))
        if self.requestDecoder.fields:
            return dict(zip(self.requestDecoder.fields, values))
        return values

    def formatResponse(self, result):
        """Pack a mock response using replyEncoder.

        - dict result  + replyEncoder.fields -> values ordered by fields, then packed
        - tuple result + replyEncoder        -> packed directly via struct.pack
        - other types                        -> delegated to base
        """
        if self.replyEncoder is not None:
            fmt = self.replyEncoder.format
            fields = self.replyEncoder.fields
            if isinstance(result, dict) and fields:
                values = tuple(result[f] for f in fields)
                return bytearray(struct.pack(fmt, *values))
            if isinstance(result, tuple):
                return bytearray(struct.pack(fmt, *result))
        return super().formatResponse(result)

    def buildSendData(self, **params):
        """Build outgoing bytes from requestEncoder + named params + defaults.
        Falls back to self.data when requestEncoder is not set."""
        if self.requestEncoder is None:
            return self.data
        merged = dict(self.requestEncoder.defaults)
        merged.update(params)
        values = tuple(merged[f] for f in self.requestEncoder.fields)
        return struct.pack(self.requestEncoder.format, *values)

    def unpackReply(self, replyBytes):
        """Unpack reply bytes via replyDecoder.format.
        Returns raw bytes if replyDecoder is not set."""
        if self.replyDecoder is None or not self.replyDecoder.format:
            return replyBytes
        return struct.unpack(self.replyDecoder.format, replyBytes)

    def send(self, port) -> bool:
        try:
            port.writeData(data=self.data, endPoint=self.endPoints[0])
            self.isSent = True
            if self.replyDecoder is not None and self.replyDecoder.length > 0:
                self.reply = port.readData(length=self.replyDecoder.length)
            self.isSentSuccessfully = True
        except Exception as err:
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            raise

        return False
