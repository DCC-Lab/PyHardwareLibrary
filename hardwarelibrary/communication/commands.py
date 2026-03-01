import re
import struct

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
        raise NotImplementedError("Subclasses must implement the send() command")

    def matches(self, inputBytes):
        return False

    def extractParams(self, inputBytes):
        return ()

    def formatResponse(self, result):
        if result is None:
            return None
        elif isinstance(result, (bytes, bytearray)):
            return bytearray(result)
        elif isinstance(result, str):
            return bytearray(result.encode('utf-8'))
        return None

class TextCommand(Command):
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
        parts = re.split(r'\{[^}]*\}', self.text)
        escaped = [re.escape(p) for p in parts]
        return '(.+?)'.join(escaped)

    @property
    def effectiveMatchPattern(self):
        if self.matchPattern is not None:
            return self.matchPattern
        return self._autoMatchPattern

    def matches(self, inputBytes):
        try:
            inputStr = inputBytes.decode('utf-8', errors='replace')
        except Exception:
            return False
        return re.match(self.effectiveMatchPattern, inputStr) is not None

    def extractParams(self, inputBytes):
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
        if self._prefix is not None:
            return self._prefix
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
        if self.requestFormat is not None:
            unpackLen = struct.calcsize(self.requestFormat)
            if len(inputBytes) >= unpackLen:
                values = struct.unpack(self.requestFormat, bytes(inputBytes[:unpackLen]))
                if self.requestFields is not None:
                    return dict(zip(self.requestFields, values))
                return values
        return ()

    def formatResponse(self, result):
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
