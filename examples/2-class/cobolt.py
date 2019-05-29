try:
    import serial as SP
except:
    exit("pyserial must be installed with: pip install pyserial")

""" Class-oriented strategy to talk to the Cobolt
laser, change its power. See manual in ../manuals/ page 27"""

class CoboltLaser:

    def __init__(self, portName):
        """ portName : "COM1", "/dev/xxx", etc... 
        opens automatically on creation """
        self.port = None
        self.port = SP.Serial(portName)

    def __del__(self):
        if self.port is not None:
            self.port.close()

    def setPower(self, powerInWatts):
        command = "p {0:0.3f}\r".format(powerInWatts)
        data = bytearray(command, "utf-8")
        self.port.write(data)
        reply = self.port.readline()
        print(reply)

    def power(self):    
        self.port.write(b'pa?\r') 
        reply = self.port.readline()
        print(reply)
        power = float(reply.decode())
        return power


if __name__ == "__main__":
    try:
        laser = CoboltLaser("COM1")
    except:
        exit("No laser found on COM1")

    laser.setPower(powerInWatts=0.1)
    print("Power is {0:0.3f} W".format(laser.power()))
