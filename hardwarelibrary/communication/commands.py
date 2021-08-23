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
    def __init__(self, name, text, replyPattern = None, 
                                   alternatePattern = None, 
                                   multiReplyCount = 1,
                                   finalReplyPattern = None, 
                                   endPoints = (None, None)):
        Command.__init__(self, name, endPoints=endPoints)
        self.text : str = text
        self.replyPattern: str = replyPattern
        self.alternatePattern: str = alternatePattern
        self.multiReplyCount = multiReplyCount
        self.finalReplyPattern = finalReplyPattern

    def send(self, port, params=None) -> bool:
        try:
            self.isSent = True
            if params is not None:
                textCommand = self.text.format(params)
            else:
                textCommand = self.text

            port.writeString(string=textCommand, endPoint=self.endPoints[0])

            if self.multiReplyCount > 1:
                self.reply = []
                self.matchGroups = []

                for i in range(self.multiReplyCount):
                    reply, matchGroups = port.readMatchingGroups(
                                   replyPattern=self.replyPattern,
                                   alternatePattern=self.alternatePattern,
                                   endPoint=self.endPoints[1])
                    self.reply.append(reply)
                    self.matchGroups.append(matchGroups)

            elif self.finalReplyPattern is not None:
                self.reply = []
                self.matchGroups = []

                while True:
                    reply, matchGroups = port.readMatchingGroups(
                                   replyPattern=self.replyPattern,
                                   alternatePattern=self.alternatePattern,
                                   endPoint=self.endPoints[1])
                    self.reply.append(reply)
                    self.matchGroups.append(matchGroups)

                    if re.search(self.finalReplyPattern, reply) is not None:
                        break
            else:
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


class DataCommand(Command):
    def __init__(self, name, data, replyHexRegex = None, replyDataLength = 0, unpackingMask = None, endPoints = (None, None)):
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
                raise NotImplementedError("DataCommand reply pattern not implemented")
                # self.reply = port.readData(length=self.replyDataLength)
            self.isSentSuccessfully = True
        except Exception as err:
            
            self.exceptions.append(err)
            self.isSentSuccessfully = False
            raise(err)

        return False
