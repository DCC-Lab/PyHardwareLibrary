import serial

port = Serial("COM1")

# Read power
port.write(b'pa?\r')
reply = port.readline()
print(reply)

# Set power
port.write(b'p 0.01\r')
# There is no reply

# Read power again
port.write(b'pa?\r')
reply = port.readline()
print(reply)

port.close()