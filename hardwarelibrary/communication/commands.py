import re

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

class TextCommand(Command):
    def __init__(self, name, text, replyPattern = None, 
                                   alternatePattern = None, 
                                   endPoints = (None, None)):
        Command.__init__(self, name, endPoints=endPoints)
        self.text : str = text
        self.replyPattern: str = replyPattern
        self.alternatePattern: str = alternatePattern

    @property
    def payload(self):
        return self.text

    @property
    def numberOfArguments(self):
        match = re.search(r"\{(.*?)\}", self.text)
        if match is None:
            return 0
        return len(match.groups())

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
    def __init__(self, name, data, replyHexRegex = None, replyDataLength = 0, unpackingMask = None, endPoints = (None, None)):
        Command.__init__(self, name, endPoints=endPoints)
        self.data : bytearray = data
        self.replyHexRegex: str = replyHexRegex
        self.replyDataLength: int = replyDataLength
        self.unpackingMask:str = unpackingMask

    @property
    def payload(self):
        return self.data

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
