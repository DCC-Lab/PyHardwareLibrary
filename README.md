# PyHardwareLibrary
A simple device-oriented library with communication port for controlling devices

## Quick start
You will find a simple, trivial script named `cobolt.py` to change the power of the Cobolt laser. There are four versions, you should read the examples :

1. `1-simple`: a very trivial implementation with simple commands in sequence
2. `2-class`: a class implementation of `CoboltLaser` that partially encapsulates the details and exposes a few functions: `setPower()` and `power()`
3. `3-class+debugPort`: a class implementation with a debug port that mimicks the real device
4. The main part of the code has a `CoboltDevice` that supports `turnOn()` `turnOff()`, `setPower()` and `power()`

## Strategy

How does one go about supporting a new device? What is the best strategy?

1. Obtain manual.  Look for connectivity information. 

   1. If necessary, a driver may need to be installed to serialize the device (to make it appear as a serial port).
   2. If not available, direct USB access may be needed with libusb and PyUSB
   3. Figure out (ideally through testing, see next point) how to connect with `SerialPort` or `USBPort`, both derived classes from `CommunicationPort`

2. Identify commands and write very simple tests with `CommunicationPort`  to confirm connectivity and validate command syntax (see the other [section](#Testing-serial-ports) below for more details):

   ```python
       class TestCoboltSerialPort(unittest.TestCase):
   				def testLaserOn(self):
   					self.port = CommunicationPort("COM5")
   					self.port.writeStringExpectMatchingString('l1\r',replyPattern='OK')
   
   ```

3. Create a `DebugSerialPort`, based on `CommunicationPort` or replicating the behaviour of `SerialPort()` to mimic a real serial port.  See `CoboltDebugSerial` for an example.

4. Complete *serial* tests that will test both the real port and the debug port. Both must behave identicially.

5. Start wrapping the complex serial communication inside a `PhysicalDevice`-derivative (e.g., `LaserSourceDevice`, `LinearMotionDevice`, etc…). For an example, see `CoboltDevice` which derives from `LaserSourceDevice`.  For more details on the strategy for `PhysicalDevice`, see the section : PhysicalDevice implementation.

6. Write a series of device tests.  For examples, see `testCoboltDevice`.

7. In your device, you must be able to use your `DebugSerialPort`.  That way, the `testCoboltDevice` can run both on a real device and a debug device.

8. When all tests pass (`Port`, `DebugPort`, `Device`, `DebugDevice`), you are done


## Testing serial ports

When testing serial ports, we want to test both the real connection to a given device and a mock implementation (*e.g,* `DebugPort`) that behaves like it.  Hence, we want to run a series of tests on each port. The best strategy to run a series of tests on two different instances is the following:

1. Create a `BaseTestCases` class that does not inherit from `unittest.TestCase`, with an internal class that does inherit from `unittest.TestCases`:

   ```python
   class BaseTestCases:

      class TestCoboltSerialPort(unittest.TestCase):
         self.port = None

         ...
   ```


2. Declare variables that are useful for the test (`self.port` for instance).

3. Do not define `setUp()` or `tearDown()`

4. Populate the class with all test methods you need, with names that start with `test*`:
   ```python
   class BaseTestCases:
   
    class TestCoboltSerialPort(unittest.TestCase):
        port = None
   
        def testCreate(self):
            self.assertIsNotNone(self.port)
   
        def testCantReopen(self):
            self.assertTrue(self.port.isOpen)
            with self.assertRaises(Exception) as context:
                self.port.open()
        ...
   ```

5. In the same file, define two test subclasses that inherit from `BaseTestCases` with `setUp()` and `tearDown()` mehods that are specific to either the real port or debug port. They will therefore inherit all the methods from the parent class `BaseTestCases` and have all test methods.

   ```python
   class TestDebugCoboltSerialPort(BaseTestCases.TestCoboltSerialPort):
       def setUp(self):
          self.port = CommunicationPort(port=CoboltDebugSerial())
          self.assertIsNotNone(self.port)
          self.port.open()
   
       def tearDown(self):
          self.port.close()
   
   class TestRealCoboltSerialPort(BaseTestCases.TestCoboltSerialPort):
      def setUp(self):
          try:
                self.port = CommunicationPort(port="COM5")
                self.port.open()
          except:
                raise unittest.SkipTest("No cobolt serial port at COM5")
      def tearDown(self):
          self.port.close()
   ```

6. If you have test methods that are specific to a given port, then define them in the specific class.

7. Add the following at the end of the file:

   ```python
   if __name__ == '__main__':
       unittest.main()
   ```

8. By running the tests in this file with `python testCoboltSerial.py`, the unittest framework will automatically run all tests from both `TestDebugCoboltSerialPort` and `TestRealCoboltSerialPort`.  Of course, both should pass all tests for success.

9. This strategy can be reused to test a `Device` and its `DebugDevice` counterpart.



## PhysicalDevice implementation

A real physical device is now simple to handle: errors can occur at any time (because of the device itsefl), because the user did not connect it or did not turn it on, because the device is in an irregular  state (e.g., it reached the end of the travel range for instance).  Hence, it becomes important to handle errors gracefully but especially robustly for a class to be useful.

The strategy used by the present library is the following:

1. Many properties of devices are common: the have a USB vendor ID, a product ID, a serial number etc…  This is included in a parent class called `PhysicalDevice` that is the parent to all devices.
2. Many methods are also common: all devices must be initialized, shutdown, etc… These methods are defined in the parent class, but call the device-specific method of the derived class. For instance, `initializeDevice()` does a bit of housekeeping (is the device already initialized? was the underlying initializing successful?) and calls `doInitializeDevice` that must be implemented by the derived class. If initialization fails, it must raise an error. The class must confirm the device responds to at least one internal command to confirm it is indeed the expected device.
3. For specific classes of devices (e.g., `LaserSourceDevice`), specific methods are used to hide the details of the implementation: `LaserSourceDevice.turnOn()`, `LaserSourceDevice.power()`, `LaserSourceDevice.setPower()`, etc… These methods call device-specific methods with similar names (prefixed by `do`) in the derived class (e.g., `doTurnOn()`)
4. Methods that start with `do` *will communicate* with the device through the serial port.  They must store the result of the request into an instance variable (to cache the value and to avoid to go back to the serial port each time the value is needed). For instance, an instance `self.power` stores the result obtained from `doGetPower()`.
5. `do` methods are *never* called by users.  Users call the `turnOn()` method but not the `doTurnOn()` method. If Python as a language allowed it, the `do` methods would be hidden and private, but it does not look possible: the only convention is to use `_do` but it is only a convention, functions can still be called.
