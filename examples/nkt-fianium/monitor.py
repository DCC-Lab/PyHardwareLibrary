try:
	import serial as SP
	import time
except ImportError:
	exit("pyserial must be installed with: pip install pyserial")

""" Read-only monitor: polls the Fianium while someone turns the
physical pump current potentiometer on the chassis. Never writes a
command that changes laser state (no M=, Q=, R=, I=, X=). """

port = SP.Serial("/dev/cu.usbserial-A6008r40", baudrate=19200, timeout=0.5)

def query(command):
	port.reset_input_buffer()
	port.write(command + b"\r")
	reply = port.read(300).decode(errors="ignore")
	return reply.split("\n")[0].strip()

duration_seconds = 30
interval_seconds = 2

for i in range(int(duration_seconds / interval_seconds)):
	alarms = query(b"A?")
	temperature = query(b"T?")
	back_reflection = query(b"B?")
	preamp = query(b"P?")
	drive = query(b"Q?")
	print("[{0:5.1f}s] {1} | {2} | back_refl={3} | preamp={4} | {5}".format(
		i * interval_seconds, alarms, temperature, back_reflection, preamp, drive))
	time.sleep(interval_seconds)

port.close()
