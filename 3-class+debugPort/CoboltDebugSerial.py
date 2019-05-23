class CoboltDebugSerial:
    def __init__(self):
        self.outputBuffer = bytearray()
        self.lineEnding = b'\r'
        self.power = 0.1
        self.requestedPower = 0
        self.isOpen = False

    def open(self):
        if self.isOpen:
            raise IOError()
        else:
            self.isOpen = True

        return

    def close(self):
        if not self.isOpen:
            raise IOError()
        else:
            self.isOpen = False

        return

    def read(self, length) -> bytearray:
        data = bytearray()
        for i in range(0, length):
            if len(self.outputBuffer) > 0:
                byte = self.outputBuffer.pop(0)
                data.append(byte)
            else:
                raise CommunicationReadTimeout("Unable to read data")

        return data


    def write(self, data:bytearray) -> int :
        string = data.decode('utf-8')

        match = re.search("pa\\?", string)
        if match is not None:
            replyData = bytearray("{0}\r".format(self.power), encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("p\\?", string)
        if match is not None:
            replyData = bytearray("{0}\r".format(self.requestedPower), encoding='utf-8')
            self.outputBuffer.extend(replyData)
            return len(data)

        match = re.search("p (\\d+\\.?\\d+)\r", string)
        if match is not None:
            self.power = match.groups()[0]
            return len(data)

        raise ValueError("Unknown command: {0}".format(data))

    def readline(self) -> bytearray:
        data = bytearray()
        byte = b''
        while byte != self.lineEnding:
            if len(self.outputBuffer) > 0:
                byte = self.outputBuffer.pop(0)
                data.append(byte)
            else:
                break

        return data
