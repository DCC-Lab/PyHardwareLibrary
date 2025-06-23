import socket
import sys
import time
from struct import *

HOST, PORT = "10.211.55.4", 9999
data = bytearray(b'\x01')
data = data*int(sys.argv[1])
payload = len(data)
packetCounts = int(sys.argv[2])
messageSize = packetCounts*payload

# Create a socket (SOCK_STREAM means a TCP socket)
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.connect((HOST, PORT))
    # Connect to server and send data
    print("Sending")
    sock.sendall(pack('<I',(messageSize)))
    for i in range(packetCounts):
        sock.sendall(data)
    print("Done.")

    # Receive data from the server and shut down
    start = time.time()
    
    totalReceived = 0
    while totalReceived < messageSize:
        received = sock.recv(4096)
        totalReceived += len(received)
#    sock.shutdown(1)
    sock.close()

print("Sent:     {0}".format(messageSize))
print("Received: {0}".format(totalReceived))
print("Rate {0}".format( payload*packetCounts/(time.time()-start)/1e6))