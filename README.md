# PyHardwareLibrary

A simple device-oriented library for controlling hardware devices in the laboratory. Currently very limited but in active development.

## What is the purpose of this hardware library?

We often need to control devices in the laboratory (linear stages, spectrometers, cameras, shutters, etc...).  The drivers provided by many companies are a good start, but integrating the devices in custom software sometimes gets difficult. This Python module was created to faciliate the development of drivers and applications for hardware that is often used in the lab. It originates from a (private) project that I personnally maintained for nearly 10 years where drivers were written in Objective-C for more than 30 different devices used in my laboratory.  However, Python is more commonly taught in school and supports all platforms, therefore I started this project so that I can 1) teach how to go about developing simple drivers, 2) teach good programming practices to students, 3) get the hardware working for my own lab regardless of the platforms used (we use macOS and Windows).

Python also has the quality of being a very nice team player: it is fairly easy to integrate Python with anything, on any platform and the community is extremely active.  It is obvious by the numerous Python SDKs from companies, the thousands of modules on PyPi.org, and the support from all vendors (Microsoft, Apple and Linux). 

## Getting started

To use this module, you need to install it by downloading it then typing: `python setup.py install`.

Right now, the only useful devices supported are the Ocean Insight spectrometers, `USB2000` and `USB4000`. If you only want to use it, then the following two-line script will do:

```python
from hardwarelibrary.spectrometers import OISpectrometer

OISpectrometer.displayAny()
```

The first supported spectrometer connected will be chosen and a window will appear displaying the spectrum.

## Getting started with coding

But maybe your interest is not just using the devices, but also learning how to code to control them. You should find extensive documentation here on how to proceed.

You will find a simple, trivial script named `cobolt.py` to change the power of the Cobolt laser. There are four versions, you should read all the examples :

1. `1-simple`: a very trivial implementation with simple commands in sequence
2. `2-class`: a class implementation of `CoboltLaser` that partially encapsulates the details and exposes a few functions: `setPower()` and `power()`
3. `3-class+debugPort`: a class implementation with a debug port that mimicks the real device
4. The main part of the code has a `CoboltDevice` that supports `turnOn()` `turnOff()`, `setPower()` and `power()`

This is just a very simple example with a laser that probably few people have access to.

### Strategy

How does one go about supporting a new device? What is the best strategy?

1. Obtain the manual.  Look for connectivity information (typically, I search for `ASCII` in the text). You will find information such as "baud rate, stop bits, hardware handshake and ASCII commands"

   1. If you can't get the manual from the web site, contact the company.  As mentionned above, many will gladly help you: they usually want to sell devices or satisfy customers who did buy them.
   
2. Connect to the device, one way or another

   1. If necessary, a driver may need to be installed to serialize the device (to make it appear as a serial port).
   2. If not available, direct USB access may be needed with `libusb` and `PyUSB`.  This is the most elegant solution, but requires some knowledge of USB.  `PyHardwareLibrary` makes use of `PyUSB` extensively.
   3. Figure out (ideally through testing, see next point) how to connect with `SerialPort` or `USBPort`, both derived classes from `CommunicationPort`

3. Identify commands and write very simple tests with `SerialPort`  to confirm connectivity and validate command syntax (see the other [section](#Testing-serial-ports) below for more details):

   ```python
       class TestCoboltSerialPort(unittest.TestCase):
   				def testLaserOn(self):
   					self.port = SerialPort("COM5") # Are settings right? Baud rate, stop bits, etc...
   					self.port.writeStringExpectMatchingString('l1\r',replyPattern='OK')
   
   ```

4. Create a `DebugSerialPort`, based on `CommunicationPort`  replicating the behaviour of `SerialPort()` to mimic a real serial port.  See `CoboltDebugSerial` for an example.

5. Complete *serial* tests that will test both the real port and the debug port. Both must behave identicially.

6. *This part is not fully implemented yet:* Start wrapping the complex serial communication inside a `PhysicalDevice`-derivative (e.g., `LaserSourceDevice`, `LinearMotionDevice`, etc…). For an example, see `CoboltDevice` which derives from `LaserSourceDevice`.  For more details on the strategy for `PhysicalDevice`, see the section : `PhysicalDevice` implementation.

7. Write a series of device tests.  For examples, see `testCoboltDevice`.

8. In your device, you must be able to use your `DebugSerialPort`.  That way, the `testCoboltDevice` can run both on a real device and a debug device.

9. When all tests pass (`Port`, `DebugPort`, `Device`, `DebugDevice`), you are done

### Testing serial ports

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



### PhysicalDevice implementation

*This part is not fully implemented yet.*

Communicating with the device through serial ports is the first step.  However, most of the time, we care about some tasks we want to do with the device (turn on and use laser, acquire spectrum from spectrometer, etc...).  Therefore, after having figured out what the commands are and how the device responds, it is important to "wrap" or encapsulate all of those commands inside a class (or object) that represents the device to the end-user and make it easy to use without having to know the details. `PyHardwareLibrary` uses a base class called `PhysicalDevice` 

A real physical device is not simple to handle: errors can occur at any time (because of the device itsefl), because the user did not connect it or did not turn it on, because the device is in an irregular  state (e.g., it reached the end of the travel range for instance).  Hence, it becomes important to handle errors gracefully but especially robustly.

The strategy used by the present library is the following:

1. Many properties of devices are common: the have a USB vendor ID, a product ID, a serial number etc…  This is included in a parent class called `PhysicalDevice` that is the parent to all devices.
2. Many methods are also common: all devices must be initialized, shutdown, etc… These methods are defined in the parent class, but call the device-specific method of the derived class. For instance, `initializeDevice()` does a bit of housekeeping (is the device already initialized? was the underlying initializing successful?) and calls `doInitializeDevice` that must be implemented by the derived class. If initialization fails, it must raise an error. The class must confirm the device responds to at least one internal command to confirm it is indeed the expected device.
3. For specific classes of devices (e.g., `LaserSourceDevice`), specific methods are used to hide the details of the implementation: `LaserSourceDevice.turnOn()`, `LaserSourceDevice.power()`, `LaserSourceDevice.setPower()`, etc… These methods call device-specific methods with similar names (prefixed by `do`) in the derived class (e.g., `doTurnOn()`)
4. Methods that start with `do` *will communicate* with the device through the serial port.  They must store the result of the request into an instance variable (to cache the value and to avoid to go back to the serial port each time the value is needed). For instance, an instance `self.power` stores the result obtained from `doGetPower()`.
5. `do` methods are *never* called by users.  Users call the `turnOn()` method but not the `doTurnOn()` method. If Python as a language allowed it, the `do` methods would be hidden and private, but it does not look possible: the only convention is to use `_do` but it is only a convention, functions can still be called.



## Motivation

I must also vent my frustration that end-user software from the manufacturers is often abysmaIly-designed, buggy and/or simply frustrating to use. I have even seen example code from companies that simply does not even compile. Others will only support Windows 7, and even say it with a straight face in 2021 like it's totally normal. On top of that, many companies will claim (erroneously) that their hardware cannot run on macOS, my platform of choice.  This is usually because of shear laziness or straight out incompetence: as long as it can connect to the computer, it can be supported.  For USB devices, it is often **trivial** to write a "driver" to support a device with appropriate documentation, and I have done it on numerous occasions. Shout out to Sutter Instruments, ActiveSilicon, Hamamatsu, Ocean Insight, and Thorlabs for being friendly to developers: they provide all the necessary information upon request and are of great help to scientists. On the other hand, here is a finger🖕 to many other companies I will not name here, but many camera providers come to mind and a prominent National company that makes Instruments in the US wins the grand prize.