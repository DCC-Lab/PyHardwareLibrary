try:
	import serial as SP
except ImportError:
	exit("pyserial must be installed with: pip install pyserial")

""" Simplest, most trivial strategy to talk to this (old) Fianium
supercontinuum laser.

This is NOT the NKT Interbus protocol that pylablib.devices.NKT speaks:
an Interbus scan on this unit finds nothing. This unit runs its own
ASCII command-line firmware instead (confirmed reply to V?: "Issue 5.17
20th February 2012"). 19200 baud, commands terminated by \\r (not \\r\\n).
Send 'help\\r' for the full command list. """

port = SP.Serial("/dev/cu.usbserial-A6008r40", baudrate=19200, timeout=0.5)

def send(command):
	port.reset_input_buffer()
	port.write(command + b"\r")
	return port.read(500)

print(send(b"V?"))  # software version
print(send(b"T?"))  # chassis temperature
print(send(b"A?"))  # alarms

port.close()
