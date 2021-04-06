import socketserver
from struct import *

class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        try:
            # self.request is the TCP socket connected to the client
            self.data = self.request.recv(2)
            packetCounts = unpack('<h',self.data)[0]
            self.data = bytearray()
            for i in range(packetCounts):
                self.data += self.request.recv(4096)
            print("{0} sent {1} bytes in {2} packets".format(self.client_address[0], len(self.data), packetCounts))
            
            self.request.sendall(self.data)
        except Exception as err:
            print("Server exception: {0}. Had received {1} bytes.".format(err, len(self.data)))

if __name__ == "__main__":
    HOST, PORT = "127.0.0.1", 9999

    try:
        socketserver.TCPServer.allow_reuse_address = True
        # Create the server, binding to localhost on port 9999
        with socketserver.TCPServer((HOST, PORT), MyTCPHandler) as server:
            # Activate the server; this will keep running until you
            # interrupt the program with Ctrl-C
            server.serve_forever()
    except Exception as err:
        print(err)

