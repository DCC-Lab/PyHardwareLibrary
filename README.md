# PyHardwareLibrary

A simple device-oriented library for controlling hardware devices in the laboratory.

You may be here for one of two things:

1. You want to use a device (e.g., Ocean Insight spectrometer), get data, and save it.
2. You want to program a driver to get a new device to work on your computer.

If this applies to you, then keep reading.

## Learning more

If you are interested in learning more about:

* **USB itself** and connectivity details, please read [README-USB.md](README-1-USB.md).
* **RS-232 and its relation to USB**, please read [README-RS232.md](README-2-RS232.md)
* **experimenting with an RS-232 chip from FTDI**, please read [DAQ I/O with UM232R (french only)](https://github.com/dccote/Enseignement/blob/4c8eca0c7ca7ec74c60774af57483f5d77fb60be/DAQ/Semaine-02.pdf). You can probably Google translate or DeepL translate the Markdown file [here](https://github.com/dccote/Enseignement/blob/4c8eca0c7ca7ec74c60774af57483f5d77fb60be/DAQ/Semaine-02.md).
* **USB Cameras**, please read [README-USB-Cameras.md](README-3-USB-Cameras.md)
* how `PyHardwareLibrary` **deals with the many different ports**, please read [README-Communication ports.md](README-5-Communication-ports.md)
* **the process involved in supporting a new device** in  `PyHardwareLibrary` but also in general, please read [README-New-device-coding-example.md](README-4-New-device-coding-example.md)

It would be a good plan to read all of the above, essentially in that order.

## What is the purpose of this hardware library?

We often need to control devices in the laboratory (linear stages, spectrometers, cameras, shutters, etc...).  The drivers provided by many companies are a good start, but integrating the devices in custom software sometimes gets difficult. This Python module was created to **facilitate the development of drivers**,  **facilitate the creation of applications**, and **provide minimal but useful applications** for hardware that is often used in the lab. It originates from a (private) project that I personnally maintained for nearly 10 years where drivers were written in Objective-C and included support for more than 30 different devices used in my laboratory.  However, Python is more commonly taught in school and supports essentially all platforms, therefore I started this project so that I can 1) teach how to go about developing simple drivers, 2) teach good programming practices to students, 3) get the hardware working for my own lab regardless of the platforms used (we use macOS and Windows), 4) get help to shorten the development cycles to support more devices.

Why Python? Python is object-oriented (essential) and offers reasonable performance. Python also has the quality of being a very nice team player: it is fairly easy to integrate Python with anything, on any platform and the community is extremely active.  It is obvious by the numerous Python SDKs from companies, the thousands of modules on PyPi.org, and the support from all vendors (Microsoft, Apple and Linux). Python is also not a dead language: I am very pleased to see the language evolve over the years with new language features and new standard modules. 

## Getting started with using devices

To use this module, you need to install it by [downloading it](https://github.com/DCC-Lab/PyHardwareLibrary/archive/refs/heads/master.zip) from GitHub then typing: `python setup.py install`.

Right now, the only useful devices supported are the Ocean Insight spectrometers, `USB2000` and `USB4000`. If you only want to use it, then the following two-line script will do:

```python
from hardwarelibrary.spectrometers import OISpectrometer

OISpectrometer.displayAny()
```

The first supported spectrometer connected will be chosen and a window will appear displaying the spectrum.

If you want to do more such as integrating it in some other software you are writing, at this point the best option is to type `help(someClass)` to get the help from the code:

```python
>>> from hardwarelibrary.spectrometers import OISpectrometer
>>> help(OISpectrometer)

Help on class OISpectrometer in module hardwarelibrary.spectrometers.oceaninsight:

class OISpectrometer(builtins.object)
 |  OISpectrometer(idProduct, model, serialNumber=None)
 |  
 |  An Ocean insight (Ocean Optics) spectrometer.  This allows complete access
 |  to the hardware with simple functions to get the spectrum, or modify the
 |  integration time. It is the base class for all Ocean Insight Spectrometers,
 |  but you will not instantiate this directly: use USB2000() or USB4000(),
 |  or simply: OISpectrometer.any() to get any spectrometer.
 |  
 |  Access to the device is done with pyusb and does not require any
 |  additional information. The USB-specific attributes of the spectrometers are
 |  available,  but are not needed for standard usage.  If you need to
 |  implement additional functions and communicate with the device (not all
 |  capabilities are currently coded), then you could implement them in a
 |  separate function.
 |  [...]
 |  getCalibration(self)
 |      Get the hardcoded calibration from the spectrometer.  It is a
 |      3rd-order polynomial. Currently, no nonlinearities are considered.
 |  
 |  getIntegrationTime(self)
 |      Get the integration time in as a float value in milliseconds
 |      cls.timeScale is 1 for ms and 1000 if it is stored in µs
 |  
 |  getParameter(self, index)
 |      Get any of the 20 parameters hardcoded into the spectrometer.
 |      
 |      Parameters
 |      ----------
 |      
 |      index: int
 |          0 – Serial Number
 |          1 – 0th order Wavelength Calibration Coefficient 
 |          2 – 1st order Wavelength Calibration Coefficient
[...]

```



Of course, other devices will be supported in the near future.  As mentionned elsewhere in this document, the present `PyHardwareLibrary` project originates from a private `HardwareLibrary` project that supports many different devices, such as Sutter Instruments stages, many Thorlabs devices (stages, shutters, rotation stages, flip mirrors), Spectra Physics Lasers, Cobolt Lasers, Olympus microscopes, GenTech-EO power meters, LabJack, Zaber, Marzhauer, Prior, Newport, Intellidrive, so it is a question of time (and need) before they are ported to `PyHardwareLibrary`.

## Getting started with coding for new devices

But maybe your interest is not just in using the devices, but also in learning how to code to control them. You should find extensive documentation here on how to proceed.

You will find a simple, trivial script named `cobolt.py` to change the power of a Cobolt laser. There are three versions, you should read all three examples :

1. `1-simple`: a very trivial implementation with simple commands in sequence
2. `2-class`: a class implementation of `CoboltLaser` that partially encapsulates the details and exposes a few functions: `setPower()` and `power()`
3. `3-class+debugPort`: a class implementation with a debug port that mimicks the real device
4. The main part of the code has a `CoboltDevice` that supports `turnOn()` `turnOff()`, `setPower()` and `power()`

This is just a very simple example with a laser that probably few people have access to, but should give a general idea.

### Strategy

How does one go about supporting a new device? What is the best strategy?

1. Obtain the manual.  Look for connectivity information (typically, search for `ASCII` or `serial` in the text). You will find information such as "baud rate, stop bits, hardware handshake" and most importantly "ASCII or binary commands". This is what you need.

   1. If you can't get the manual from the web site, contact the company.  As mentionned above, many will gladly help you: they usually want to sell devices or satisfy customers who did buy them.
   
2. Connect to the device, one way or another.

   1. If necessary, a driver may need to be installed to serialize the device (to make it appear as a serial port). In this case, you would use the `SerialPort` class after having installed that driver. 
      1. Not all devices can appear as a "serial port".  Simple devices (e.g. a translation stage) are fine because they simply read commands ('MOVE") and reply ("OK").  However, others (camera, spectrometers) respond to commands and transmit data, sometime a lot of it and require many communication lines.  The USB standard provides that (with *endpoints*), but not the old-style serial port that essentially is just a two-way communication on a single channel. 
      2. Also, for a device to appear as a serial port, the manufacturer needs to provide a certain amount of information in the USB descriptor of the device. If they don't, you are out of luck.
   2. If standard serial ports are not available, direct USB access may be needed with `libusb` and `PyUSB`.  This is the most elegant solution, but requires some knowledge of USB.  `PyHardwareLibrary` makes use of `PyUSB` extensively, and `USBPort` simplifies communication.
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



## Design goals

*This part is not fully implemented yet in this library, but was implemented in a separate project.*

Communicating with the device through serial ports is the first step.  However, most of the time, we care about some tasks we want to do with the device (turn on and use laser, acquire spectrum from spectrometer, etc...).  Therefore, after having figured out what the commands are and how the device responds, it is important to "wrap" or encapsulate all of those commands inside a class (or object) that represents the device to the end-user and make it easy to use without having to know the details. `PyHardwareLibrary` uses a base class called `PhysicalDevice` 

A real physical device is not simple to handle: errors can occur at any time (because of the device itself), because the user did not connect it or did not turn it on, because the device is in an irregular  state (e.g., it reached the end of the travel range for instance).  Hence, it becomes important to handle errors gracefully but especially robustly.

The strategy used by the present library is the following:

1. Many properties of devices are common: the have a USB vendor ID, a product ID, a serial number etc…  This is included in a parent class called `PhysicalDevice` that is the parent to all devices.
2. Many methods are also common: all devices must be initialized, shutdown, etc… These methods are defined in the parent class, but call the device-specific method of the derived class. For instance, `initializeDevice()` does a bit of housekeeping (is the device already initialized? was the underlying initializing successful?) and calls `doInitializeDevice` that must be implemented by the derived class. If initialization fails, it must raise an error. The class must confirm the device responds to at least one internal command to confirm it is indeed the expected device.
3. For specific classes of devices (e.g., `LaserSourceDevice`), specific methods are used to hide the details of the implementation: `LaserSourceDevice.turnOn()`, `LaserSourceDevice.power()`, `LaserSourceDevice.setPower()`, etc… These methods call device-specific methods with similar names (prefixed by `do`) in the derived class (e.g., `doTurnOn()`)
4. Methods that start with `do` *will communicate* with the device through the serial port.  They must store the result of the request into an instance variable (to cache the value and to avoid to go back to the serial port each time the value is needed). For instance, an instance `self.power` stores the result obtained from `doGetPower()`.
5. `do` methods are *never* called by users.  Users call the `turnOn()` method but not the `doTurnOn()` method. If Python as a language allowed it, the `do` methods would be hidden and private, but it does not look possible: the only convention is to use `_do` but it is only a convention, functions can still be called.



## Motivation

I must also vent my frustration that end-user software from the manufacturers is often abysmaIly-designed, buggy and/or simply frustrating to use but most of the time, all of the above. I have even seen example code from companies that simply does not even compile. Others will only support Windows 7, and even say it with a straight face in 2021 like it's totally normal. On top of that, many companies will claim (erroneously) that their hardware cannot run on macOS, my platform of choice.  This is usually because of shear laziness or straight out incompetence: as long as it can connect to the computer, it can be supported.  For USB devices, it is often **trivial** to write a "driver" to support a device with appropriate documentation, and I have done it on numerous occasions. The rule of thumb is that the companies that have good software say, on Windows, usually have good software on many platforms, as they obviously understand how to program and undertand the simplicity of writing cross-platform code if you make it a design requirement. On the other hand, I have found that lack of support for platforms other than Windows usually translates in fairly crappy software on Windows anyway: these companies tend to be hardware companies that consider software only secondary and probably farm it out.  Shout out to ActiveSilicon, Sutter Instruments, Hamamatsu, Ocean Insight (for their documentation but certainly not for their software), and Thorlabs for being friendly to developers: they provide all the necessary information upon request and are of great help to scientists. On the other hand, here is a middle finger🖕 to many other companies I will not name here, but many camera providers come to mind (some located near *Princeton* University) as well as a prominent company that rhymes with *ationalinstruments* that wins the grand prize for its uselessness and overall incompetence at providing anything useful in software to their end users for the last 20 years despite producing great hardware (somebody should also let them know that more than 12 pixels can be used to draw icons because this <img src="README.assets/automation.png" alt="automation" style="zoom:200%;" /> with a big red x in it apparently represents "automation" and this <img src="README.assets/Am.png" alt="Am" style="zoom:200%;" /> is "amplitude modulation". It would be funny if it wasn't so sad).

## Contact

Prof. Daniel Côté, Ph.D. and P.Eng, dccote@cervo.ulaval.ca

Group web site: http://www.dcclab.ca

Youtube channel: http://www.youtube.com/user/dccote

