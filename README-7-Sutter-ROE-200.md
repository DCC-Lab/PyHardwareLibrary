# This document is incomplete and contains error

Do not use yet.



## An example: Sutter ROE-200

Let's look at a classic from microscopy and neuroscience, the MPC-385 XYZ stage from Sutter Instruments with its ROE-200 controller. The manual is available [here](https://github.com/DCC-Lab/PyHardwareLibrary/blob/cd7bf0cf6256ba4dbc6eb26f0657c0db59b35848/hardwarelibrary/manuals/MPC-325_OpMan.pdf) or on their web site, and it is sufficiently detailed for us (it also has a few omissions that we will find).  When we connect the device, we can inspect its **USB Descriptors**. We then find out that the idVendor is 4930, the idProduct is 1. We can pick a USB configuration, pick a USB interface, then the inspection of the endpoint descriptors tells us it has two endpoints: one IN, one OUT. 

```python
device = usb.core.find(idVendor=4930, idProduct=1) # Sutter Instruments has idVendor 4930 or 0x1342
if device is None:
    raise IOError("Can't find device")

device.set_configuration()                         # first configuration
configuration = device.get_active_configuration()  # get the active configuration
interface = configuration[(0,0)]                   # pick the first interface (0) with no alternate (0)

outputEndpoint = interface[0]                      # First endpoint is the output endpoint
inputEndpoint = interface[1]                       # Second endpoint is the input endpoint

```

### Commands

Once we have dientified the device, we need to send commands and read replies.  Please note that this is not possible with `PyUSB` because we need to send "serial" commands to the FDTI chips. Typically, the Sutter ROE-200 will be recognized by the FTDI driver, but on Big Sur (Summer 2021), their driver was modified and does not recognize it yet.  But we can use PyFTDI (which itself uses PyUSB) to send our commands to the Sutter Device.

It is a very simple device, because it has a very limited set of commands it accepts. It can **move**, it can tell you its **position**.  There are other commands, but they will not be critical here and we will not implement them.

<img src="/Users/dccote/GitHub/PyHardwareLibrary/README.assets/image-20210415195905341.png" alt="image-20210415195905341" style="zoom:25%;" /><img src="/Users/dccote/GitHub/PyHardwareLibrary/README.assets/image-20210415195013040.png" alt="image-20210415195013040" style="zoom: 24%;" />

Let's look at the anatomy of the **Get Current Position** command: it is the `C` character (which has an ASCII code of 0x43), and the documentation says that the total number of bytes is two for the command. Reading other versions of the manual and discussing with Sutter tells us that all commands are followed by a carriage return `\r`  (ASCII character 0x0d). So if we send this command to the device, it should reply with its position.

The reply will be 13 bytes: it will consist of 3 values for X, Y and Z coordinates, encoded as `signed long integers` (32 bits or 4 bytes).  Closing this will be the carriage return `\r`, indicated at the top of the next page, for a total of 13 bytes.

### Sending GetPosition command

Python has `byte` and `bytearray` objects. The `b` indicates that the string of text must be interpreted as bytes. We pick the OUT endpoint, and send the command with:

```python
commandBytes = bytearray(b'C\r')
outputEndpoint.write(commandBytes)
```

### Reading GetPosition reply

We read the 13 bytes from the input endpoint:

```python
replyBytes = inputEndPoint.read(size_or_buffer=13)
```

If everything goes well, the last byte will be the character `\r`.  We know from the documentation that these 13 bytes represent 3 signed long integers and a character. Python has a function to `pack` and `unpack` this data. The function is described [here](https://docs.python.org/3/library/struct.html), and the format that corresponds to our binary data is `<lllc`: Little-endian (<), three long ('l') and a letter ('c') 

```python
x,y,z, lastChar = unpack('<lllc', replyBytes)

if lastChar == b'\r':
    print("The position is {0}, {1}, {2}".format(x,y,z))
else:
    print('Error in reply: last character not 0x0d')
   
```

### Sending MovePosition command

To move the stage to a different position, we need to encode (i.e. `pack`) the positions we want into binary data. This is done with:

```python
# We already have the position in x,y and z. We will move a bit from there.
commandBytes = pack('<clllc', ('M', x+10, y+10, z+10, '\r'))
outputEndpoint.write(commandBytes)
```

### Reading MovePosition reply

The stage will move and will send a `\r` when done, as per the documentation.

```python
replyBytes = inputEndPoint.read(size_or_buffer=1)
lastChar = unpack('<c', replyBytes)

if lastChar != b'\r':
    print('Error: incorrect reply character')
    
```

The complete code, repackaged with functions, is available here:

```python
# this file is called sutter.py
import usb.core
import usb.util
from struct import *

device = usb.core.find(idVendor=4930, idProduct=1) # Sutter Instruments has idVendor 4930 or 0x1342
if device is None:
    raise IOError("Can't find device")

device.set_configuration()                         # first configuration
configuration = device.get_active_configuration()  # get the active configuration
interface = configuration[(0,0)]                   # pick the first interface (0) with no alternate (0)

outputEndpoint = interface[0]                      # First endpoint is the output endpoint
inputEndpoint = interface[1]                       # Second endpoint is the input endpoint

def position() -> (int,int,int):
    commandBytes = bytearray(b'C\r')
    outputEndpoint.write(commandBytes)

    replyBytes = inputEndPoint.read(size_or_buffer=13)
    x,y,z, lastChar = unpack('<lllc', replyBytes)

    if lastChar == b'\r':
        return (x,y,z)
    else:
        return None
  
def move(position) -> bool:
    x,y,z  = position
    commandBytes = pack('<clllc', ('M', x, y, z, '\r'))
    outputEndpoint.write(commandBytes)
    
    replyBytes = inputEndPoint.read(size_or_buffer=1)
		lastChar = unpack('<c', replyBytes)

    if lastChar != b'\r':
        return True
    
    return False
    
```

## Encapsulating the USB device in a class

We may have communicated with the device, but it would still be tedious to use:

1. We will need to include this code in any Python script that manipulates the device
2. We have variables floating around (`device`, `interface`, `inputEndpoint`, `outputEndpoint`), they will prevent us from using them again (they are global).
3. We have to keep track of the position ourselves and convert to microns manually: currently the position is in micro steps
4. Our error management is minimal.  For instance, what if the device does not reply in time? 

It would be preferable to have a single object (i.e. the sutter device), and that that object 1) manages the communication without us, 2) responds to `moveTo` and `position`, 3) keeps track of its position, manage it and really, isolates us from the details? We don't really care that it communicates through USB and that there are "endpoints".  All we want is for the device to **move** and tell us **its position**.  We can therefore create a `SutterDevice` class that will do that: *a class hides the details away inside an object that keeps the variables and the functions to operate on these variables together.*

```python
# This file is called bettersutter.py
import usb.core
import usb.util
from struct import *

class SutterDevice:
    def __init_(self):
      self.device = usb.core.find(idVendor=4930, idProduct=1) 
			if device is None:
    		raise IOError("Can't find Sutter device")

      self.device.set_configuration()        # first configuration
      self.configuration = self.device.get_active_configuration()  # get the active configuration
      self.interface = self.configuration[(0,0)]  # pick the first interface (0) with no alternate (0)

      self.outputEndpoint = self.interface[0] # First endpoint is the output endpoint
      self.inputEndpoint = self.interface[1]  # Second endpoint is the input endpoint
      
      self.microstepsPerMicrons = 16

    def positionInMicrosteps(self) -> (int,int,int):
      commandBytes = bytearray(b'C\r')
      outputEndpoint.write(commandBytes)

      replyBytes = inputEndPoint.read(size_or_buffer=13)
      x,y,z, lastChar = unpack('<lllc', replyBytes)

      if lastChar == b'\r':
        return (x,y,z)
      else:
        return None
  
  	def moveInMicrostepsTo(self, position) -> bool:
      x,y,z  = position
      commandBytes = pack('<clllc', ('M', x, y, z, '\r'))
      outputEndpoint.write(commandBytes)

      replyBytes = inputEndPoint.read(size_or_buffer=1)
      lastChar = unpack('<c', replyBytes)

      if lastChar != b'\r':
        return True

      return False
    
    def position(self) -> (float, float, float):
			position = self.positionInMicrosteps()
      if position is not None:
          return (position[0]/self.microstepsPerMicrons, 
                  position[1]/self.microstepsPerMicrons,
                  position[2]/self.microstepsPerMicrons)
      else:
          return None
      
  	def moveTo(self, position) -> bool:
      x,y,z  = position
      positionInMicrosteps = (x*self.microstepsPerMicrons, 
                              y*self.microstepsPerMicrons,
                              z*self.microstepsPerMicrons)
      
      return self.moveInMicrostepsTo( positionInMicrosteps)

    def moveBy(self, delta) -> bool:
      dx,dy,dz  = delta
      position = self.position()
      if position is not None:
          x,y,z = position
          return self.moveTo( (x+dx, y+dy, z+dz) )
			return True

if __name__ == "__main__":
    device = SutterDevice()

    x,y,z = device.position()
    device.moveTo( (x+10, y+10, z+10) )
    device.moveBy( (-10, -10, -10) )
```

Notice how:

1. We don't know the implementation details, yet it fully responds to our needs: it can move and tell us where it is.
2. We can make other convenience functions that make use of the two key functions (`moveInMicrostepsTo` and `positionInMicrosteps`). For instance, we can create a `moveBy` function that will take care of getting the position for us then increase it and send the move command.
3. We still may have problems if the communication with the device does not go as planned.
4. If the device is not connected, or not on, the code will fail with no other options than to restart the program.



### Robust encapsulation

We can still improve things. In this version:

1. The device does not need to be connected for the `SutterDevice` to be created.

2. The write and read functions are limited to two functions that can manage any errors gracefully: if there is any error, we shutdown everything and will initialize the device again on the next call.

3. Minimal docstrings (Python inline help) is available.

    

```python
# This file is called bestsutter.py
import usb.core
import usb.util
from struct import *

class SutterDevice:
    def __init_(self):
      """
      SutterDevice represents a XYZ stage.  
      """
      self.device = None
      self.configuration = None
      self.interface = None
      self.outputEndpoint = None
      self.inputEndpoint = None
     
      self.microstepsPerMicrons = 16

    def initializeDevice(self):
      """
      We do a late initialization: if the device is not present at creation, it can still be
      initialized later.
      """

      if self.device is not None:
        return
      
      self.device = usb.core.find(idVendor=4930, idProduct=1) 
      if self.device is None:
        raise IOError("Can't find Sutter device")

      self.device.set_configuration()        # first configuration
      self.configuration = self.device.get_active_configuration()  # get the active configuration
      self.interface = self.configuration[(0,0)]  # pick the first interface (0) with no alternate (0)

      self.outputEndpoint = self.interface[0] # First endpoint is the output endpoint
      self.inputEndpoint = self.interface[1]  # Second endpoint is the input endpoint
    
    def shutdownDevice(self):
      """
      If the device fails, we shut everything down. We should probably flush the buffers also.
      """
      
      self.device = None
      self.configuration = None
      self.interface = None
      self.outputEndpoint = None
      self.inputEndpoint = None
      
    def sendCommand(self, commandBytes):
      """ The function to write a command to the endpoint. It will initialize the device 
      if it is not alread initialized. On failure, it will warn and shutdown."""
      try:
        if self.outputEndpoint is None:
          self.initializeDevice()
          
        self.outputEndpoint.write(commandBytes)
      except Exception as err:
        print('Error when sending command: {0}'.format(err))
        self.shutdownDevice()
    
    def readReply(self, size, format) -> tuple:
      """ The function to read a reply from the endpoint. It will initialize the device 
      if it is not already initialized. On failure, it will warn and shutdown. 
      It will unpack the reply into a tuple, and will remove the b'\r' that is always present.
      """

      try:
        if self.outputEndpoint is None:
          self.initializeDevice()

        replyBytes = inputEndPoint.read(size_or_buffer=size)
        theTuple = unpack(format, replyBytes)
        if theTuple[-1] != b'\r':
           raise RuntimeError('Invalid communication')
        return theTuple[:-1] # We remove the last character
      except Exception as err:
        print('Error when reading reply: {0}'.format(err))
        self.shutdownDevice()
        return None
      
    def positionInMicrosteps(self) -> (int,int,int):
      """ Returns the position in microsteps """
      commandBytes = bytearray(b'C\r')
      self.sendCommand(commandBytes)
      return self.readReply(size=13, format='<lllc')
  
    def moveInMicrostepsTo(self, position):
      """ Move to a position in microsteps """
      x,y,z  = position
      commandBytes = pack('<clllc', ('M', x, y, z, '\r'))
      self.sendCommand(commandBytes)
      self.readReply(size=1, format='<c')
    
    def position(self) -> (float, float, float):
      """ Returns the position in microns """

      position = self.positionInMicrosteps()
      if position is not None:
          return (position[0]/self.microstepsPerMicrons, 
                  position[1]/self.microstepsPerMicrons,
                  position[2]/self.microstepsPerMicrons)
      else:
          return None
      
    def moveTo(self, position):
      """ Move to a position in microns """

      x,y,z  = position
      positionInMicrosteps = (x*self.microstepsPerMicrons, 
                              y*self.microstepsPerMicrons,
                              z*self.microstepsPerMicrons)
      
      self.moveInMicrostepsTo( positionInMicrosteps)

    def moveBy(self, delta) -> bool:
      """ Move by a delta displacement (dx, dy, dz) from current position in microns """

      dx,dy,dz  = delta
      position = self.position()
      if position is not None:
          x,y,z = position
          self.moveTo( (x+dx, y+dy, z+dz) )

if __name__ == "__main__":
    device = SutterDevice()

    x,y,z = device.position()
    device.moveTo( (x+10, y+10, z+10) )
    device.moveBy( (-10, -10, -10) )
```

We have made significant progress, but there are still problems or at least areas that can be improved:

1. The code above has not been fully tested.  How do we test this? Is it necessary? The solution will be **Unit Testing**. *Hint*: when we do, we will learn that the **move** command actually sends a 0x00 byte at a regular interval when the move is taking a long time. This is not in the documentation but it sure is in the device. 
2. In fact, the code above was not tested at all, because I don't have the device on my computer, it is only in the lab and I wrote the code from home.  It would be nice to be able to test even without the device connected, especially when we integrate this code into other larger projects. The solution will be a mock (i.e. fake) **DebugSutterDeviceUSBPort** that behaves like the real thing. This will require abstracting away the **USBPort** itself.
3. Error management is not easy with hardware devices. They can fail, they can be disconnected, they can be missing, the firmware in the device can be upgraded, etc... If the command times out, what are you supposed to do? Can you recover? The solution is a more general class **PhysicalDevice** that can manage these aspects, while offering enough flexibility to adapt to any type of device. The is the strategy behind **PyHardwareLibrary**.
4. We are putting a lot of work in this Sutter Instrument stage, but what if it breaks and your supervisor purchases or borrows another device (say a Prior)?  Should you change all your code? It is, after all, just another linear stage. The solution to this is a **LinearMotionDevice** base class that will offer a uniform set of functions to move and get the position, without knowing any details about the device itself. This way, the **SutterDevice** will inherit from **LinearMotionDevice**, and a new **PriorDevice** would also inherit from it and could act as a perfect substitute. This approach, which requires time investment in the short term, will limit the impact of any change in the future.  You can take a look at [**OISpectrometer**](https://github.com/DCC-Lab/PyHardwareLibrary/blob/c6fa50b932945388bb5bfce443669158275c5db4/hardwarelibrary/spectrometers/oceaninsight.py) in the PyHardwareLibrary for an example, where two spectrometers can be used interchangeably since they both derive from OISpectrometer, which can return a **USB2000** or a **USB4000** depending on what is connected.