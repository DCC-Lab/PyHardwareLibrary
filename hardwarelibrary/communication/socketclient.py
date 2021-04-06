import socket
import sys
from struct import *
import time

HOST, PORT = "127.0.0.1", 9999
data = bytearray(b'\x01')
data = data*int(sys.argv[1])
payload = len(data)
packetCounts = int(sys.argv[2])


start = time.time()
# Create a socket (SOCK_STREAM means a TCP socket)
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect((HOST, PORT))
    # Connect to server and send data

    sock.sendall(pack('<h',(packetCounts)))
    for i in range(packetCounts):
	    sock.sendall(data)

    # Receive data from the server and shut down
    
    totalReceived = 0
    while totalReceived < payload*packetCounts:
        received = sock.recv(4096)
        totalReceived += len(received)
#    sock.shutdown(1)
    sock.close()

print("Sent:     {0}".format(len(data)))
print("Received: {0}".format(totalReceived))
print("Rate {0}".format( payload*packetCounts/(time.time()-start)/1e6))