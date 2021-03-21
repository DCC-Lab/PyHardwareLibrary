from hardwarelibrary.communication import SerialPort
from hardwarelibrary.lasersources import CoboltDevice

laser = CoboltDevice(bsdPath="COM5")

laser.initializeDevice()
laser.turnAutostartOff()
laser.turnOn()
print(laser.isLaserOn())
laser.setPower(0.01)
print(laser.power())
print(laser.interlock())
laser.turnAutostartOn()
print(laser.isLaserOn())
