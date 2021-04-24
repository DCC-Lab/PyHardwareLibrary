

# General communication strategies

You are here because you are interested in discussing general strategies to communicate with devices (any devices) and control them in the lab. In particular, the present document will discuss port abstraction in the context of device control.  It would appear tedious in the first place to :

1. Set up communication
2. Manage communication
3. Send commands, read replies
4. Analyze answer and determine the information hidden in it. Deal with units, floating point numbers, scientific notation, text
5. Deal with errors when a command does not respond as expected.

Very often we will have a pattern that looks like: 1. Send text command 2. Analyze text reply 3. extract a number (e.g., a power value for instance), and really, this is with any type of device (old-style serial, USB, GPIB, Ethernet, etc...).  

## The problems to solve

1. Managing ports is a hardware issue that should be of minor interest to us
2. Managing the dialog with the devices must be robust and general enough to avoid always going through the same strategies to analyze the reply.

## Solutions

The solutions to these two problems are the following:

1. A general class that offers all the "hooks" for any communication port, without dealing with the specific (`CommunicationPort`)
2. General methods in `CommunicationPort` that will offer more than just hardware-level communication but rather general "dialog methods" to deal with a command, its reply and the analysis of the reply (this will be Regular-expression based methods, or `regex`). These methods will be available to any port that derives from `CommunicationPort`.
3. Another level of abstraction that encapsulates a `TextCommand` or a `DataCommand` and deals with all the details of sending the command, getting the reply and managing errors.

## 1. CommunicationPort

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

`PyUSB`  already offers everything we need, so why would we need another class `CommunicationPort` on top? You can already see part of the answer in the previous script: writing the command to the port is simple, but reading the result as a string requires a few steps (assign buffer, read into buffer, convert to string). We would prefer to have something like this:

```python
port = USBPort(idVendor=0x1ad5, idProduct=0x0300) # Hypothetical class we want

port.writeString('*VER')
version = port.readString()
```

and maybe other functions (as we will see below) so we can focus on the device, not the communication with the device. The class `CommunicationPort` serves this purpose and can be found [here](https://github.com/DCC-Lab/PyHardwareLibrary/blob/ea4b05308662a26b583c6477c41b1cfb2cdc776f/hardwarelibrary/communication/communicationport.py). The idea is to always go through two key functions to read and write data (which will be highly specific to the port being used by the subclass), and code any other functions to go through those. Here are the basic primitive functions that we need for any kind of port:

1. `open()` the port
2. `flush()` the port of any remaining characters (in case of errors, and when opening).
3. confirm port `isOpen`
4. `writeData()` to the port
5. `readData()` from the port
6. `close()` the port

Here is an excerpt below in `CommunicationPort`:

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

[ ... more to be described later ... ]

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

```



Another class called `SerialPort` makes use of Python POSIX library to communicate with devices, and is considered a port with one output endpoint and one input endpoint.

So at this point, we have the technical details of the port managed.  What about the dialog, or the message-reply loop we will go through when controlling the device? 

## 2. Dialog-based methods to send commands and read replies

This section will digress for a minute and discuss the details of regular expressions (or `regex`) and their use when communicating with devices.

### The problem that regular expressions solve

Regular expressions allow you to recognize patterns in text and extract information from them. From a programmer's curiosity that took root with obscure Unix and Linux commands `awk` and `sed`, but especially the Perl language, they are now standardized and available in almost all programming languages. It is a powerful tool for working with any form of text. In the case of the scientist or engineer, let's think of the following situations:

* Dealing with series of files in a general way.
* Isolating dates
* Recognizing numbers, figures, etc...

For example: You want to extract the first and last name of a person in the following text:

`Côté, Daniel`

So you want the word before the comma, then, after the spaces, the other word. You could read the characters one by one, but what if you have the following name?

`De Koninck, Yves`

The analysis can get more and more complicated and twisted. So, rather than reading the characters one by one and doing the analysis, you can use regular expressions that were invented to describe just such patterns. In this case, you could quickly extract the first and last name with the following regular expression:

`\s*(\S.+?),\s*(\S.*?)\s*`

The parentheses in the regular expression represent *matching groups*. In our case, the first expression between brackets is the name, the second the first name, without the spaces that may or may not be present before or after the name. In the first case, we would have "Côté" and "Daniel", while in the second case we would have "De Koninck" and "Yves".

### The basic language of regular expressions

In their simplest form, a regular expression is a sequence of characters with a repetition indicator. The capture parentheses allow to keep the text that was recognized. It can then be referred to in a way that depends on the programming tool used ($1, $2, ... in Perl, \1 \2, ... in the "Find" box of Sublime Text, etc.).

| Expression | Signification | Expression | Signification |
| ----------------- | ---------------------------- | ---------- | ----------------------------------------------------- |
| . | N'importe quel caractère | * | 0 ou plusieurs fois |
| \s | Espace blanc (ou tabulation) | + | 1 un plusieurs fois |
| \S | Tout sauf un espace blanc | ? | 0 ou 1 fois |
| \d | Un chiffre | {n} | n fois |
| \D | Tout sauf un chiffre | {n,m} | entre n et m fois |
| ^ | Début de ligne | *? | 0 ou plusieurs fois, mais priorité au prochain patron |
| $ | Fin de ligne | () | Parenthèses de capture |
| Lettre ou chiffre | La lettre ou le chiffre | (?:) | Paranthèse de regroupement sans capture |
| \\. | Le point | [abc] | a or b or c |
| \\\\ | Le caractère \\ | | |

### Examples of regular expressions

| Object | Expression |
| ------------------------------------------------------------ | --------------------------------------------------- |
| file name | ```(.\*?)\\.(...)``` |
| file name and path | ```(.\*?)/(.\*?)\\.(...)``` |
| A date like AAA-MM-JJ | ```(\\d{4})-(\d\d)-(\d\d)``` |
| A filename with fichier-XXX-YYY-ZZZ.tif where XXX, YYY et ZZZ sont des chiffres | ```fichier-(\\d{3})-(\\d{3})-(\\d{3})\\.tif{1,2}``` |
| A floating point number | `[+-]?\d(\.\d*)?` |
| An signed integer | `[+-]?\d+` |
| Scientific notation number | `[+-]?\d(\.\d+)?[Ee][+-]?\d+` |

### Regex in Python

Python supports regular expressions. They are used as follows to extract numerical values in a two-column table in a Markdown file (for example: `| 2.0 | 4.0 |` but also `| .02 | 0.01 |`):

```python
import re

matchObj = re.match("\||s*(\.?\d+.?\d*)\s*||s*(\.?\d+.?\d*)\s*", line)
if matchObj:
	value = float(matchObj.group(1))
	x.append(value)
	value = float(matchObj.group(2))
	y.append(value)
	continue
```

### How this fits with CommunicationPort

We can create functions that will write a command and read a reply, validate that it conforms to a regular expression, and possibly extract  certain values:

```python
    def writeStringExpectMatchingString(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
        with self.transactionLock:
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])
            match = re.search(replyPattern, reply)
            if match is None:
                if alternatePattern is not None:
                    match = re.search(alternatePattern, reply)
                    if match is None:
                        raise CommunicationReadAlternateMatch(reply)
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}'".format(replyPattern))

        return reply

    def writeStringReadFirstMatchingGroup(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
        with self.transactionLock:
            reply, groups = self.writeStringReadMatchingGroups(string, replyPattern, alternatePattern, endPoints)
            if len(groups) >= 1:
                return reply, groups[0]
            else:
                raise CommunicationReadNoMatch("Unable to find first group with pattern:'{0}' in {1}".format(replyPattern, groups))

    def writeStringReadMatchingGroups(self, string, replyPattern, alternatePattern = None, endPoints=(None,None)):
        with self.transactionLock:
            self.writeString(string, endPoints[0])
            reply = self.readString(endPoints[1])

            match = re.search(replyPattern, reply)

            if match is not None:
                return reply, match.groups()
            else:
                raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))

    def readMatchingGroups(self, replyPattern, alternatePattern = None, endPoint=None):
        reply = self.readString(endPoint=endPoint)

        match = re.search(replyPattern, reply)

        if match is not None:
            return reply, match.groups()
        else:
            raise CommunicationReadNoMatch("Unable to match pattern:'{0}' in reply:'{1}'".format(replyPattern, reply))

```

Important points to notice:

1. Notice how it does not assume any type of communication port, it simply makes use of the primitive `readString` and `writeString`,  which are automatically implemented in all subclasses because each subclass implements `readData` and `writeData`. 
2. I will describe in more details the `portLock` and  `transactionLock` later, but it is important to appreciate (while you may not understand the details) that if we have a *multi-threaded application*:
   1. we do not want any other functions to access the port while we are accessing it. This is the purpose of `portLock`: we get exclusive access while we need it becausw we block anybody else trying to.
   2. if we write a command where we expect a reply, we don't want anyone to send another command while we are waiting for our reply. This is the purpose of `transactionLock`: a transaction in the HardwareLibrary module is a combination command-reply. most devices do not accept multiple commands before the previous one is not processed.

## 3. Encapsulate the command-reply behaviour in a Command class

This will be discussed later, but  `Command`, `TextCommand` and `DataCommand` classes are defined to manage everything in a single entity. 95% of the time, we send a command, read a reply and extract a value from the reply, then do something with this value. This can be encapsulated in a class that will manage all the details for us.

