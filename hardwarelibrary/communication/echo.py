from communication import CommunicationPort

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
