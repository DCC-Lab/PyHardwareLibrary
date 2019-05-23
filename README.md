# PyHardwareLibrary
A simple device-oriented library with CommunicationPort for controlling devices

## Quick start
You will find a simple, trivial script named `cobolt.py` to change the power of the Cobolt laser. There are three versions: you should read the three examples :

1. `1-simple`: a very trivial implementation with simple commands in sequence
2. `2-class`: a class implementation of `CoboltLaser` that partially encapsulates the details and exposes a few functions: `setPower()` and `power()`
3. `3-class+debugPort`: a class implementation with a debug port that mimicks the real device
4. The main part of the code has a `CoboltDevice` that supports `turnOn()` `turnOff()`, `setPower()` and `power()`



## Strategy

How does one go about supporting a new device? What is the best strategy?

1. Obtain manual.  Look for connectivity information. 

   1. If necessary, a driver may need to be installed to serialize the device (make it appear as a serial port).
   2. If not, direct access with USB may be needed.

2. Identify commands and write very simple tests with `CommunicationPort`  to confirm connectivity and validate command syntax:

   ```python
       class TestCoboltSerialPort(unittest.TestCase):
   				def testLaserOn(self):
   					self.port = CommunicationPort("COM5")
   					self.port.writeStringExpectMatchingString('l1\r',replyPattern='OK')
   
   ```

3. Create a `DebugSerialPort`, based on `CommunicationPort` or replicating `Serial()` to mimic the behaviour of the real serial port.  See `CoboltDebugSerial` for an example.

4. Complete *serial* tests that will test both the real port and the debug port.Both must behave identicially.

5. Start wrapping the complex serial communication inside a `PhysicalDevice`-derivative (e.g., `LaserSourceDevice`, `LinearMotionDevice`, etc…). For an example, see `CoboltDevice` which derives from `LaserSourceDevice`.

6. Write a series of device tests.  For examples, see `testCoboltDevice`.

7. In your device, you must be able to use your `DebugSerialPort`.  That way, the `testCoboltDevice` can run both on a real device and a debug device.

8. When all tests pass, you are done.

   