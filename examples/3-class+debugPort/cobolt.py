try:
    import serial as SP
except:
    exit("pyserial must be installed with: pip install pyserial")
import re

class CoboltDebugSerial:
    def __init__(self):
        self.outputBuffer = bytearray()
        self.lineEnding = b'\r'
        self.power = 0.1
        self.requestedPower = 0
        self.isOpen = True

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

""" Class-oriented strategy to talk to the Cobolt
laser, change its power. See manual in ../manuals/ page 27"""

class CoboltLaser:

    def __init__(self, portName):
        """ portName : "COM1", "/dev/xxx", etc... 
        opens automatically on creation """
        self.port = None
        if portName == "debug":
            self.port = CoboltDebugSerial()
        else:
            self.port = SP.Serial(portName)

    def __del__(self):
        if self.port is not None:
            self.port.close()

    def setPower(self, powerInWatts):
        command = "p {0:0.3f}\r".format(powerInWatts)
        data = bytearray(command, "utf-8")
        self.port.write(data)
        reply = self.port.readline()

    def power(self):    
        self.port.write(b'pa?\r') 
        reply = self.port.readline()
        power = float(reply.decode())
        return power


if __name__ == "__main__":
    try:
        laser = CoboltLaser("COM1")
    except:
        laser = CoboltLaser("debug")

    laser.setPower(powerInWatts=0.1)
    print("Power is {0:0.3f} W".format(laser.power()))

    laser.setPower(powerInWatts=0.01)
    print("Power is {0:0.3f} W".format(laser.power()))

    laser.setPower(powerInWatts=0.001)
    print("Power is {0:0.3f} W".format(laser.power()))
    
