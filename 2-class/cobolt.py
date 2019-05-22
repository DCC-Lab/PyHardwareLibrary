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
        self.port = SP.Serial(portName)

    def __del__(self):
        self.port.close()

    def setPower(self, powerInWatts):
        command = "p {0:0.3f}\r".format(powerInWatts)
        data = bytearray(command, "utf-8")
        self.port.write(data)

    def power(self):    
        port.write(b'pa?\r') 
        reply = port.readline()
        power = float(reply.decode("utf-8") )
        return power


if __name__ = "__main__":
    laser = CoboltLaser("COM1")
    laser.setPower(powerInWatts=0.1)
    print(laser.power())
    
