try:
	import serial as SP
	import time
except:
	exit("pyserial must be installed with: pip install pyserial")

""" Simplest, most trivial strategy to talk to the Cobolt
laser, change its power. See manual in ../manuals/ page 27"""

port = SP.Serial("COM1") # Use '/dev/xxx on macOS'

""" Read laser power. Note: 
1) b'' means binary
2) ends with \r meaning ASCII 13 dec
3) readline() will read up to next \n
"""

port.write(b'pa?\r') 
reply = port.readline()
power = int(reply)
print("Power is {0}.".format(power))

# Set power
port.write(b'p 0.01\r')
reply = port.readline()
print(reply) # should print ok


# Read power again, after a delay
time.sleep(1)
port.write(b'pa?\r')
reply = port.readline()
power = int(reply)
print("Power is now {0}.".format(power))

port.close()