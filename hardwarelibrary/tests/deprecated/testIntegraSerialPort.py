# This script is called firstIntegraCommunication.py
import unittest
from array import array

import usb.core
import usb.util


class TestIntegraPort(unittest.TestCase):
    def setUp(self):
        device = usb.core.find(idVendor=0x1ad5, idProduct=0x0300) # Find our device
        if device is None:
            raise (unittest.SkipTest("No Integra devices connected"))

    def testFirstCommunication(self):
        device = usb.core.find(idVendor=0x1ad5, idProduct=0x0300) # Find our device
        if device is None:
            raise IOError("Can't find device")

        device.set_configuration()                                     # First (and only) configuration
        configuration = device.get_active_configuration()              # Confirm configuration
        interface = configuration[(0,0)]                               # Get the first interface, no alternate

        interruptEndpoint = interface[0]                               # Not useful
        outputEndpoint = interface[1]                                  # Our output bulk OUT
        inputEndpoint = interface[2]                                   # Our input bulk IN

        outputEndpoint.write("*VER")                                   # The command, no '\r' or '\n'

        buffer = array('B',[0]*inputEndpoint.wMaxPacketSize)           # Buffer with maximum size
        bytesRead = inputEndpoint.read(size_or_buffer=buffer)          # Read and print as a string
        print( bytearray(buffer[:bytesRead]).decode(encoding='utf-8')) # Buffer is not resized, we do it ourselves

if __name__ == '__main__':
    unittest.main()
