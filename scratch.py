from CoboltDevice import *

laser = CoboltDevice(bsdPath="COM5")

laser.initializeDevice()
# laser.turnOn()
print(laser.isLaserOn())
laser.setPower(0.01)
print(laser.power())
print(laser.interlock())
