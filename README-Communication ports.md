

# General communication strategies

You are here because you are interested in discussing general strategies to communicate with devices (any devices) and control them in the lab. It would appear tedious in the first place:

1. Set up communication
2. Manage communication
3. Send commands, read replies
4. Analyze answer and determine the information hidden in it. Deal with units, floating point numbers, scientific notation, text
5. Deal with errors when a command does not respond as expected.

Especially with lab equipment, very often we will have a pattern that looks like: 1. Send text command 2. Analyze text reply 3. extract a number (e.g., a power value for instance).

## The problems to solve

1. Managing ports is a hardware issue that should be of minor interest to us
2. Managing the dialog with the devices must be robust and general to avoid always coding very specific methods for analyzing the text



## Solution

The solutions to these two problems are the following:

1. A general class that offers all the "hooks" for any communication port, without dealing with the specific (`CommunicationPort`)
2. General methods in `CommunicationPort` that will offer more than just hardware-level communication but rather general "dialog methods" to deal with a command, its reply and the analysis of the reply (this will be Regular-expression based methods, or `regex`).

## CommunicationPort

To communicate with devices, we could use `PyUSB` directly:

```python
# This script is called firstIntegraCommunication.py
import usb.core
import usb.util
from array import array 

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
bytesRead = inputEndpoint.read(size_or_buffer=buffer)          # Read and get number of bytes read
print( bytearray(buffer[:bytesRead]).decode(encoding='utf-8')) # Buffer is not resized, we do it ourselves
```

In general with any device, we want to : write something to the port and read the reply. `PyUSB`  already offers everything we need, so why would we need another `CommunicationPort` on top? You can already see part of the answer in the previous script: writing the command to the port is simple, but reading the result as a string requires a few steps (assign buffer, read into buffer, convert to string). We would prefer to have something like this:

```python
port = USBPort(idVendor=0x1ad5, idProduct=0x0300) # Hypothetical class we want

port.writeString('*VER')
version = port.readString()
```

and maybe other functions (as we will see below). The class `CommunicationPort` serves this purpose and can be found [here](https://github.com/DCC-Lab/PyHardwareLibrary/blob/ea4b05308662a26b583c6477c41b1cfb2cdc776f/hardwarelibrary/communication/communicationport.py). The idea here will be to always go through two key functions to read and write data (which will be highly specific to the port being used by the subclass), and code any other functions to go through those. Here are the basic primitive functions that we need for any kind of port:

1. `open()` the port
2. `flush()` the port of any remaining characters (in case of errors, and when opening).
3. confirm port `isOpen`
4. `writeData()` to the port
5. `readData()` from the port
6. `close()` the port

Here is an excerpt below:

```python
class CommunicationPort:
    """CommunicationPort class with basic application-level protocol 
    functions to write strings and read strings, and abstract away
    the details of the communication.
    """
    
    def __init__(self):
        self.portLock = RLock()
        self.transactionLock = RLock()

    @property
    def isOpen(self):
        raise NotImplementedError()

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def bytesAvailable(self) -> int:
        raise NotImplementedError()

    def flush(self):
        raise NotImplementedError()

    def readData(self, length, endPoint=None) -> bytearray:
        raise NotImplementedError()

    def writeData(self, data, endPoint=None) -> int:
        raise NotImplementedError()

    def readString(self, endPoint=None) -> str:      
        with self.portLock:
            byte = None
            data = bytearray(0)
            while (byte != b''):
                byte = self.readData(1, endPoint)
                data += byte
                if byte == b'\n':
                    break

            string = data.decode(encoding='utf-8')

        return string

    def writeString(self, string, endPoint=None) -> int:
        nBytes = 0
        with self.portLock:
            data = bytearray(string, "utf-8")
            nBytes = self.writeData(data, endPoint)

        return nBytes

[ ... more to be described later ]

```

So we can create a subclass of `CommunicationPort` that has the *specific details* of a USB port in these primitive functions, while making use of the general functions.  Here we have `USBPort` for a USB port:

```python
class USBPort(CommunicationPort):
    """USBPort class that benefits from CommunicationPort and implements the USB details of the port
    """
 
    def __init__(self, idVendor=None, idProduct=None, serialNumber=None, interfaceNumber=0, defaultEndPoints=(0, 1)):
        CommunicationPort.__init__(self)
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.serialNumber = serialNumber
        self.interfaceNumber = interfaceNumber
        self.defaultEndPointsIndex = defaultEndPoints

        self.device = None
        self.configuration = None
        self.interface = None        
        self.defaultOutputEndPoint = None
        self.defaultInputEndPoint = None
        self.defaultTimeout = 50
        self._internalBuffer = None

    def __del__(self):
        """ We need to make sure that the device is free for others to use """
        if self.device is not None:
            self.device.close()

    @property
    def isOpen(self):
        if self.device is None:
            return False    
        else:
            return True    
    @property
    def isNotOpen(self):
        return not self.isOpen

    def open(self):
        self._internalBuffer = bytearray()

        self.device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.device is None:
            raise IOError("Can't find device")

        self.device.set_configuration()
        self.configuration = self.device.get_active_configuration()
        self.interface = self.configuration[(self.interfaceNumber,0)]
        
        outputIndex, inputIndex = self.defaultEndPointsIndex
        self.defaultOutputEndPoint = self.interface[outputIndex]
        self.defaultInputEndPoint = self.interface[inputIndex]

        self.flush()

    def close(self):
        self._internalBuffer = None
        
        if self.device is not None:
            self.device.reset()
            self.device = None
            self.configuration = None
            self.interface = None        
            self.defaultOutputEndPoint = None
            self.defaultInputEndPoint = None

    def bytesAvailable(self, endPoint=None) -> int:
        return len(self._internalBuffer)

    def flush(self, endPoint=None):
        if self.isNotOpen:
            return

        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        else:
            inputEndPoint = self.interface[endPoint]
        
        with self.portLock:
            self._internalBuffer = bytearray()
            maxPacket = inputEndPoint.wMaxPacketSize
            data = array.array('B',[0]*maxPacket)
            try:
                nBytesRead = inputEndPoint.read(size_or_buffer=data, timeout=30)
                self._internalBuffer += bytearray(data[:nBytesRead])
            except:
                pass # not an error
                                
    def readData(self, length, endPoint=None) -> bytearray:
        if not self.isOpen:
            self.open()

        if endPoint is None:
            inputEndPoint = self.defaultInputEndPoint
        else:
            inputEndPoint = self.interface[endPoint]

        with self.portLock:
            while length > len(self._internalBuffer):
                maxPacket = inputEndPoint.wMaxPacketSize
                data = array.array('B',[0]*maxPacket)
                nBytesRead = inputEndPoint.read(size_or_buffer=data, timeout=self.defaultTimeout)
                self._internalBuffer += bytearray(data[:nBytesRead])

            data = self._internalBuffer[:length]
            self._internalBuffer = self._internalBuffer[length:]

        return data

    def writeData(self, data, endPoint=None) -> int:
        if not self.isOpen:
            self.open()

        if endPoint is None:
            outputEndPoint = self.defaultOutputEndPoint
        else:
            outputEndPoint = self.interface[endPoint]

        with self.portLock:
            nBytesWritten = outputEndPoint.write(data, timeout=self.defaultTimeout)
            if nBytesWritten != len(data):
                raise IOError("Not all bytes written to port")

        return nBytesWritten

    def readString(self, endPoint=None) -> str:      
        data = bytearray()
        while True:
            try:
                data += self.readData(length=1, endPoint=endPoint)
                if data[-1] == 10: # How to write '\n' ?
                    return data.decode(encoding='utf-8')
            except Exception as err:
                raise IOError("Unable to read string terminator: {0}".format(err))

```



## Dialog-based methods to send commands and read replies

This section will discuss the details of `regex` and its use for communicating with devices.