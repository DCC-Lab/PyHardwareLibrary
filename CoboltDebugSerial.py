import re
from CommunicationPort import *
import time

globalLock = RLock()

class CoboltDebugSerial:
    def __init__(self):
        self.outputBuffer = bytearray()
        self.lineEnding = b'\r'
        self.power = 0.1
        self.isOn = 0
        self.requestedPower = 0
        self.autostart = 1
        self._isOpen = True

    @property
    def is_open(self):
        return self._isOpen
    
    def open(self):
        with globalLock:
            if self._isOpen:
                raise IOError("port is already open")
            else:
                self._isOpen = True

        return

    def close(self):
        with globalLock:
            self._isOpen = False

        return

    def flush(self):
        return

    def read(self, length) -> bytearray:
        with globalLock:
            data = bytearray()
            for i in range(0, length):
                if len(self.outputBuffer) > 0:
                    byte = self.outputBuffer.pop(0)
                    data.append(byte)
                else:
                    raise CommunicationReadTimeout("Unable to read data")

        return data


    def write(self, data:bytearray) -> int :
        with globalLock:
            string = data.decode('utf-8')

            match = re.search("pa\\?", string)
            if match is not None:
                replyData = bytearray("{0:0.4f}\r\n".format(self.power), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("p\\?", string)
            if match is not None:
                replyData = bytearray("{0:0.4f}\r\n".format(self.requestedPower), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("p (\\d+\\.?\\d+)\r", string)
            if match is not None:
                requestedPower = float(match.groups()[0])
                process = Thread(target=increasePowerSlowlyInBackground, 
                                 kwargs=dict(port=self,
                                             endPower=requestedPower,
                                             duration=1.0))
                process.start() # will complete in the background
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("l\\?\r", string)
            if match is not None:
                replyData = bytearray("{0}\r\n".format(self.isOn), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("l1\r", string)
            if match is not None:
                replyData = bytearray()
                if self.autostart == 1:
                    replyData = bytearray("Syntax error: not allowed in autostart mode\r\n", encoding='utf-8')
                else:
                    self.isOn = 1
                    replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("l0\r", string)
            if match is not None:
                self.isOn = 0
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)


            match = re.search("sn\\?\r", string)
            if match is not None:
                replyData = bytearray("123456\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("@cobas 1\r", string)
            if match is not None:
                if self.autostart == 0:
                    self.isOn = 0
                else:
                    pass
                self.autostart = 1
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("@cobas 0\r", string)
            if match is not None:
                self.autostart = 0
                replyData = bytearray("OK\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)

            match = re.search("@cobas\\?\r", string)
            if match is not None:
                replyData = bytearray("{0}\r\n".format(self.autostart), encoding='utf-8')
                self.outputBuffer.extend(replyData)
                return len(data)


            match = re.search("ilk\\?\r", string)
            if match is not None:
                replyData = bytearray("1\r\n", encoding='utf-8')
                self.outputBuffer.extend(replyData)

                return len(data)

            # Error (string already includes \n)
            replyData = bytearray("Syntax error: {0}\n".format(string), encoding='utf-8')
            self.outputBuffer.extend(replyData)

        return len(data)


def increasePowerSlowlyInBackground(port, endPower, duration):
    actualPower = port.power
    delta = (endPower - actualPower)/10.0
    for i in range(10):
        with globalLock:
            try:
                port.power = actualPower + delta * (i+1)
            except:
                print("Unable to set power")
        time.sleep(0.05)
    port.power = endPower
