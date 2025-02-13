[TOC]

# Understanding the Universal Serial Bus (USB)

by Prof. Daniel Côté, Ph.D., P. Eng., dccote@cervo.ulaval.ca, http://www.dcclab.ca

You are here because you have an interest in programming hardware devices, and the communication with many of them is through the Universal Serial Bus, or USB. The USB standard is daunting to non-expert for many reasons:  because it is so general (universal), it needs to provide a solution for many, many different types of devices from mouse pointers to all-in-one printers, USB hubs, ethernet adaptors, etc. In addition, it was created to [solve problems related to the original serial port RS-232](README-RS232.md), and if you have not worked with old serial ports, some of the problems USB solves will not be apparent to you or may not even appear necessary. Therefore, when you are just trying to understand serial communications for your problem ("*I just want to send a command to my XYZ stage!*"), all this complexity becomes paralyzing.  Of course, you don't always need to program everything from scratch, like we will do here: very often, manufacturers will provide a Python Software Development Kit (or SDK) with all the work done for you. **If it exists, use it.** However, we assume here that either such an SDK is not available or you simply want to learn how they are made.  We could always sweep everything under the rug, but you are currently reading this document, so it is assumed you want to understand the details.  I hope to help you understand better from the perspective of a non-expert.

## Inspecting USB devices

Let's start by exploring with Python and PyUSB to see what these devices are telling us. We will not communicate with them directly yet, we will simply inspect them.

### Installing PyUSB and libusb

I wish we could dive right in.  I really do. If you just want to see what I do, skip and go to the exploration part ([First Steps](#first-steps)).  But if you want to explore on your computer too, then you need to install PyUSB and libusb.

The first part is simple. Install the PyUSB module with `pip`:

```sh
pip install pyusb
```

But then, you need to install `libusb`, which is the actual engine that talks to the USB ports on your computer, and PyUSB needs to know where it is. Libusb is an open source library that has been adopted by many developers because it is complete, bug-free and cross-platform, and without it, PyUSB will not work. Doing `pip install libusb` is not a solution, it is a different module and keeps the libusb "for itself". It also does not ship with the macOS libusb. You can use Zadig on Windows to install it or brew on macOS. It may also already be installed on your computer (if you see `/usr/local/lib/libusb-1.0.0.dylib` on your computer, it should work).  On macOS and Linux, install libusb with these two lines in the terminal:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install libusb
```

On Windows, get [Zadig](https://zadig.akeo.ie) and [keep for fingers crossed](https://github.com/libusb/libusb/wiki/Windows#how-to-use-libusb-on-windows). Worse comes to worst, the simplest solution is to [download](https://libusb.info) it and keep `libusb-1.0.x.dll` in the directory where you expect to keep your Python scripts (for now). Don't get me started on [DLLs on Windows](https://github.com/DCC-Lab/PyHardwareLibrary/commit/ddfaf442d61348d7ed8611f2436e43f20b450c45). If everything really does not work for one reason or another, you can use [USBView](https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/usbview) or [USBTreeView](https://www.uwe-sieber.de/usbtreeview_e.html) to at least look at the USB descriptors. If you don't believe me how much of a mess this is, look at the [solutions offered here](https://forums.raspberrypi.com/viewtopic.php?t=306298) to deal with it.

### First steps

Your computer has a USB bus, that is, a main entry point through which all USB devices that you connect will communicate. When you plug in a device, it will automatically provide basic information to identify itself. That information is hardcoded into the device and informs the computer what it is and what it can do. So the first thing we want is to list all devices currently connected to your computer through your USB bus (or busses, some computers have more than one):

```python
import usb.core
import usb.util

for bus in usb.busses():
    for device in bus.devices:
        if device != None:
            usbDevice = usb.core.find(idVendor=device.idVendor, 
                                      idProduct=device.idProduct)
            print(usbDevice)
```

I connected a Kensington Wireless presenter and Laser pointer.  I get the following **USB Device Descriptor**, which I commented for clarity:

```sh
DEVICE ID 047d:2012 on Bus 020 Address 001 =================
 bLength                :   0x12 (18 bytes)              # The length in bytes of this description
 bDescriptorType        :    0x1 Device                  # This is a USB Device Descriptor
 bcdUSB                 :  0x200 USB 2.0                 # What USB standard it complies to
 bDeviceClass           :    0x0 Specified at interface  # A class of device (here, not known yet)
 bDeviceSubClass        :    0x0                         # A subclass of device (here, not known yet)
 bDeviceProtocol        :    0x0                         # A device protocol (here, not known yet)
 bMaxPacketSize0        :    0x8 (8 bytes)               # The size of packets that will be transmitted
 idVendor               : 0x047d                         # The USB Vendor ID.  This is Kensington.
 idProduct              : 0x2012                         # The USB Product ID.  This pointer device.
 bcdDevice              :    0x6 Device 0.06              
 iManufacturer          :    0x1 Kensington              # The text description of the manufacturer
 iProduct               :    0x3 Wireless Presenter with Laser Pointer # Text name of product
 iSerialNumber          :    0x0                         # The text description of the serial number 
 bNumConfigurations     :    0x1                         # The number of USB configurations

```

Let's highlight what is important:

1. First: numbers written 0x12, 0x01 etc... are hexadecimal numbers, or numbers in base 16. Each "digit" can take one of 16 values: 0-9, then a to f representing 10 to 15. Therefore,  0x12 is 1 x 16 + 2 = 18 dec.  Lowercase or uppercase are irrelevant.  Up to 9, decimal and hexadecimal are the same.
2. The **vendor id** is unique to the vendor of this device.  This value is registered with the USB consortium for a small cost. In the present case, we can use this later to get "all devices from Kensington".
3. The **product id** is unique to a product, from Kensington.  The vendor manages their product ids as they wish.
4. The **bNumConfigurations** is the number of possible configurations this USB device can take. It will generally be 1 with scientific equipment, but it can be more than that. We will simply assume it is always 1 for the rest of the present discussion, this is not a vital part for us.
5. Don't worry about the letters (`b`, `i`, `bcd`) in front of the descriptors: they simply indicate without ambiguity how they are stored in the USB descriptor: a `b` represents a *byte* value, an `i` represents a *2-byte integer*, and a `bcd` is also a 2-byte integer, but interpreted in decimal (binary-coded-decimal). `bcdUSB`= 0x200 means 2.0.0.
6. You may be wondering how a string can be represented by an integer (say `iManufacturer`)? This is because it is not the string itself, but a string pointer to a list of strings at the end of the descriptor.  PyUSB automatically fetches the corresponding string when showing show the descriptor.

Right after connecting, the device is in an "unconfigured mode". Someone, somewhere, needs to take responsibility for this device and do something.  Again, we need to separate general user devices (mouse, printers etc...) from scientific hardware.  With user devices, the device class, subclass, vendor id, product id, and protocol are sufficient for the computer to determine whether or not it can manage it. If the computer has the driver for this device, it will "own" it and manage it.  For instance, the printer is recognized and then the operating system can do what it needs to do with it (this is [discussed below](#communicating-with-usb-devices)).  However, scientific equipement will often appear as "General Device", and the computer will likely not know what to do.  This is when we come in.

### Configuring the USB device

We need to set the device into one of its configurations.  As described before, this is most likely just setting the device in its only possible configuration. So we get the USB device using the `usb.core.find` function of PyUSB, which will just relay the request to libusb and return any device that matches the parameters we want. In our case, we specify the idVendor and the idProduct, so the only device that can match is the one we want.

```python
import usb.core
import usb.util

device = usb.core.find(idVendor=0x047d, idProduct=0x2012)  # For a Kensington pointer. Choose yours.
if device is None:
	raise IOError("Can't find device")

device.set_configuration()                        # Use the first configuration
configuration = device.get_active_configuration() # Then get a reference to it
print(configuration)
```

This will print the following **USB Configuration Descriptor**, which I am also commenting:

```sh
  CONFIGURATION 1: 100 mA ==================================
   bLength              :    0x9 (9 bytes)
   bDescriptorType      :    0x2 Configuration        # This is a USB Configuration descriptor
   wTotalLength         :   0x22 (34 bytes)
   bNumInterfaces       :    0x1                      # It has one "USB interface" (discussed below)
   bConfigurationValue  :    0x1                      # It is configuration number 1 (there is no 0).
   iConfiguration       :    0x0 
   bmAttributes         :   0xa0 Bus Powered, Remote Wakeup
   bMaxPower            :   0x32 (100 mA)
[... more stuff related to interfaces and endpoints ... ]
```

Again, the important aspects.

1. It has a configuration value of 1, which happens to be the only one. Notice that it starts at 1, not 0. 

   *In fact, some devices in the wild are distributed with a single configuration labelled '0'. This is invalid according to the standard because `set_configuration(0)` is the method to unconfigure a device and `0` is the value returned when the device is unconfigured, but nevertheless still occurred.  For a while, since it was so common, Microsoft and Apple had a workaround and still accepted 0 as a valid configuration number but around 2020 (Windows 10 and Catalina I believe), both companies stopped doing that and required changes in the devices (which is hard: this is hardcoded in the device).*

2. It says it has one **USB Interface.**  This is discussed below.

3. The configuration has some technical details, such as the fact it does not need extra power and will require 100 mA or less when connected.

### Choosing a USB interface

The best way to understand **USB interfaces** is to use an example everyone knows: all-in-one printers.  These printers-scanners can act like a printer or a scanner, yet they have a single USB cable. Sometimes they will act like a printer, sometimes they will act like a scanner, and nothing says they can't do both at the same time. The **USB Interface** is the front face or appearance of the device to the computer: the device offers a "printer interface" and a "scanner interface" and depending on what you want to do, you will choose the one you need. So this device has a single interface, let's look at it.  The above code also prints information about the interfaces of the configuration, but I had removed them for simplicity. Here is the **USB Interface Descriptor**:

```python
    INTERFACE 0: Human Interface Device ====================
     bLength            :    0x9 (9 bytes)
     bDescriptorType    :    0x4 Interface              # This is a USB Interface Descriptor
     bInterfaceNumber   :    0x0                        # It has interface number 0. It starts at 0 not 1
     bAlternateSetting  :    0x0                        
     bNumEndpoints      :    0x1                        # It has a single user-endpoint (will be number 1)
     bInterfaceClass    :    0x3 Human Interface Device # It is a type of Human Device (i.e. manipulatable)
     bInterfaceSubClass :    0x1                        # Can be available on boot
     bInterfaceProtocol :    0x1                        # 1: keyboard, 2: mouse
     iInterface         :    0x0 
[ ... more stuff about endpoints ....]
```

In this particular situation (a Kensington laser pointer), there is a single interface: 

1. The **bInterfaceClass** (0x03) says that if you choose interface #0, then you will be speaking to a Human Interface Device, which typically means keyboard, mouse, etc...  The **bInterfaceSubClass** and protocol are sufficient for the computer to determine whether or not it can manage it.  In this case, the **bInterfaceProtocol** says it acts like a keyboard.  
2. We don't need to dig deeper in Human Interface Devices at this point, but the computer will communicate with the device with accepted protocols on endpoint 0 (the "hidden", but mandatory Control Endpoint 0).
3. Some devices (in fact, most scientific equipment) will be "*serializable*".  When this information is included in the USB Interface Descriptor, the system will have sufficient information to create a virtual serial port.  At that point, the device will "appear" as a regular serial device (COM on Windows, `/dev/cu.*` on macOS and Linux). You can then connect to it like an old-style serial port just like the good ol'days with bauds, stop bits and parity, possible handshakes and all (this is a [separate discussion](README-232.md)).

### Viewing input and output endpoints

Finally, each USB interface has communication channels, or **endpoints**, that it decides to define for its purpose. An endpoint is a one-way communication either to the device (OUT) or into the computer (IN).  This Kensington Pointer has a single input enpoint, which means we cannot "talk" to it, we can only "read" from it.  Its **USB Endpoint Descriptor** is the following:

```sh
      ENDPOINT 0x81: Interrupt IN ==========================
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint     # This is a USB Endpoint Descriptor
       bEndpointAddress :   0x81 IN           # Input (because of the 0x80) and number 1.
       bmAttributes     :    0x3 Interrupt    # It is an interrupt endpoint
       wMaxPacketSize   :    0x8 (8 bytes)    # Transmists 8 bytes at a time
       bInterval        :    0xa              # Describes how fast the data will come in.

```

The important take home points are:

1. The interface will define user-endpoints (that is, endpoints that the programmer can use to talk to the device).  There are also two implicit (hidden) endpoints called endpoint #0, or the Control Endpoints. These are used to communicate "control" and USB information to the device and for our purpose (we are not making the USB chips that communicates with the device, we only want to talk to the device), then we won't need to worry about it.  We just need to know it's there.  For this reason, endpoints are numbered starting at #1.

2. You can have Endpoint #1 IN and Endpoint #1 OUT, they are different endpoints.

3. The endpoints can communicate information in various ways, and most of the time we do not care so much how it does so. Here we have an **INTERRUPT** endpoint that will provide information to the computer whenever needed. Because it is a keyboard/mouse, so we want to be responsive: it will typically refresh the position or the keys at 100 Hz.

4. My Logitech mouse has a very similar USB Device Descriptor with very similar parameters, aside from the fact that it delivers only 4 bytes of information each time :

   ```sh
   DEVICE ID 046d:c077 on Bus 020 Address 002 =================
    bLength                :   0x12 (18 bytes)
    bDescriptorType        :    0x1 Device
    bcdUSB                 :  0x200 USB 2.0
    [...]
    idVendor               : 0x046d                 # Logitech 
    idProduct              : 0xc077                 # An old optical mouse
    bcdDevice              : 0x7200 Device 114.0
   [ ... ]
     bNumConfigurations     :    0x1
     CONFIGURATION 1: 100 mA ==================================
      bLength              :    0x9 (9 bytes)
      bDescriptorType      :    0x2 Configuration
   [ ... ]
      bNumInterfaces       :    0x1
      bConfigurationValue  :    0x1
   [ ... ]
       INTERFACE 0: Human Interface Device ====================
        bInterfaceNumber   :    0x0
        bNumEndpoints      :    0x1
        bInterfaceClass    :    0x3 Human Interface Device
        bInterfaceSubClass :    0x1                 # Available on boot
        bInterfaceProtocol :    0x2                 # This is a mouse, not a keyboard
         ENDPOINT 0x81: Interrupt IN ==========================
          bLength          :    0x7 (7 bytes)
          bDescriptorType  :    0x5 Endpoint
          bEndpointAddress :   0x81 IN
          bmAttributes     :    0x3 Interrupt
          wMaxPacketSize   :    0x4 (4 bytes)       # Only 4 bytes are delivered each time
          bInterval        :    0xa
   ```

   

Finally, here is the complete **USB Device Descriptor** for my HP Envy all-in-one printer:

```sh
DEVICE ID 03f0:c511 on Bus 020 Address 001 =================
 bLength                :   0x12 (18 bytes)
 bDescriptorType        :    0x1 Device
 bcdUSB                 :  0x200 USB 2.0
 bDeviceClass           :    0x0 Specified at interface     # The class depends on the interface selected
 bDeviceSubClass        :    0x0
 bDeviceProtocol        :    0x0
 bMaxPacketSize0        :   0x40 (64 bytes)
 idVendor               : 0x03f0
 idProduct              : 0xc511
 bcdDevice              :  0x100 Device 1.0
 iManufacturer          :    0x1 HP
 iProduct               :    0x2 ENVY 4500 series
 iSerialNumber          :    0x3 CN47Q1329D05X4
 bNumConfigurations     :    0x1
  CONFIGURATION 1: 2 mA ====================================
   bLength              :    0x9 (9 bytes)
   bDescriptorType      :    0x2 Configuration
   wTotalLength         :   0x9a (154 bytes)
   bNumInterfaces       :    0x3
   bConfigurationValue  :    0x1
   iConfiguration       :    0x0 
   bmAttributes         :   0xc0 Self Powered
   bMaxPower            :    0x1 (2 mA)
    INTERFACE 0: Vendor Specific ===========================
     bLength            :    0x9 (9 bytes)
     bDescriptorType    :    0x4 Interface
     bInterfaceNumber   :    0x0
     bAlternateSetting  :    0x0
     bNumEndpoints      :    0x3
     bInterfaceClass    :   0xff Vendor Specific               # The vendor is using its own protocol
     bInterfaceSubClass :   0xcc                               # which you may know or not. I am guessing
     bInterfaceProtocol :    0x0                               # this is the scanner part
     iInterface         :    0x0 
      ENDPOINT 0x1: Bulk OUT ===============================   # 3 endpoints: bulk in/out and interrupt
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :    0x1 OUT
       bmAttributes     :    0x2 Bulk
       wMaxPacketSize   :  0x200 (512 bytes)
       bInterval        :    0x0
      ENDPOINT 0x82: Bulk IN ===============================
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :   0x82 IN
       bmAttributes     :    0x2 Bulk
       wMaxPacketSize   :  0x200 (512 bytes)
       bInterval        :    0x0
      ENDPOINT 0x83: Interrupt IN ==========================
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :   0x83 IN
       bmAttributes     :    0x3 Interrupt
       wMaxPacketSize   :   0x40 (64 bytes)
       bInterval        :    0x7
[ ... ]
    INTERFACE 1: Printer ===================================   
     bLength            :    0x9 (9 bytes)
     bDescriptorType    :    0x4 Interface
     bInterfaceNumber   :    0x1
     bAlternateSetting  :    0x0
     bNumEndpoints      :    0x2                               # Two endpoints
     bInterfaceClass    :    0x7 Printer                       # This is a printer interface
     bInterfaceSubClass :    0x1                               
     bInterfaceProtocol :    0x2
     iInterface         :    0x0 
      ENDPOINT 0x8: Bulk OUT ===============================   # Endpoint number 8 OUT to the printer
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :    0x8 OUT
       bmAttributes     :    0x2 Bulk                          # This is a BULK endpoint
       wMaxPacketSize   :  0x200 (512 bytes)                   # Large 512 bytes each packet
       bInterval        :    0x0
      ENDPOINT 0x89: Bulk IN ===============================   # Endpoint number 9 IN from the printer
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint
       bEndpointAddress :   0x89 IN
       bmAttributes     :    0x2 Bulk
       wMaxPacketSize   :  0x200 (512 bytes)                   # Large 512 bytes each packet
       bInterval        :    0x0

```

Important highlights:

1. As you can see, some USB devices can provide several interfaces and options with many endpoints.  I picked this example to highlight that the USB standard offers a really general solution for device communication, and this is why it was designed and widely accepted upon introduction. 
2. There are different types of endpoints: INTERRUPT, BULK, ISOCHRONOUS. **Bulk** is what we could call a "standard" communication channel for us, experimentalists, trying to make things work.  For the most part, we don't really need to worry about it: we will communicate with our devices and get replies.
3. Here, having all this information about my printer is not really helping me communicate with it, because I don't know what commands it will accept. This information may or may not be proprietary, and without it, there is very little hope to "program" the printer directly.

### Final words

So for a hardware programmer who wants to use a USB device, the procedure will typically be like this:

1. Find the information specific about the device you want to use, so you can find it on the bus (idProduct, idVendor, etc...).
2. Get the **USB Device Descriptor**, configure it, typically with its only **USB Configuration**.
3. Pick a **USB Interface** (in scientific equipment, there is also often only one).
4. With the **USB interface** and PyUSB, you can then use **USB Endpoints** to send (OUT) or read (IN) commands.
   1. To do so, you will need to know the details from the manufacturer.  Typically, they will tell you : "Send your commands to Endpoint 1" and "Read your replies from endpoint 2". For instance, Ocean Insight makes spectrometers and the [manual](https://github.com/DCC-Lab/PyHardwareLibrary/blob/master/hardwarelibrary/manuals/USB2000-OEM-Data-Sheet.pdf) is very clear: on page 11, it says that there are two endpoint groups (IN and OUT) number 2 and 7. Each command described in the following pages tells you where to send your command and where to read the replies from. That is a good manual from a good company that likes its users.
   2. Some companies will not provide you with the endpoints information and will just provide a list of commands for their device (assuming you will talk through the regular serial interface).  You can experiment with endpoints relatively easily to figure out which is which for simple devices. For instance, a powermeter will typically have only one IN and one OUT endpoint, so it is easy to figure out what to do.

I have not said much about *actually* communicating with devices.  On your computer, drivers provided by Microsoft, Apple and others will go through a process to determine who controls a device when it is connected.  Your first project may be to try to read the keystrokes from your keyboard or the mouse position from your optical mouse, but that will not work:  when you connect your device, the operating system has a list of "generic drivers" that will take ownership of known devices, like a mouse, keyboard, printer, etc: that is the whole point of Plug-And-Play devices. The system reads the USBDescriptors, and other details and may be able to **match** a driver to your device.  If it does so, it will **claim** the exclusive use of the interface.  Hence, if you try to communicate with a device through an interface that was already claimed by the operating system (for example, your USB keyboard or mice),  you will get an error:

```
usb.core.USBError: [Errno 13] Access denied (insufficient permissions)
```

This of course is completely expected: two programs cannot send commands at the same time to a device through the same channels, the device would have no way of knowing what to do. In addition, *listening* to a keyboard for instance would be a major security flaw, and is not possible because the access for the device will be exclusive. Therefore, we will only be able to communicate with devices that the operating system has **not matched**. Many problems on Windows originate from this: an incorrect driver is installed and claims the device (erroneously).  You then have to remove the driver from the registry to avoid having a match that prevents the right driver from controlling the device.

You will find [many articles on the web](https://github.com/libusb/libusb/wiki/FAQ#running-libusb), that describe how to claim an interface that was already claimed. On Linux, [you can actually call](https://github.com/libusb/libusb/wiki/FAQ#can-i-run-libusb-application-on-linux-when-there-is-already-a-kernel-driver-attached-to-it) `libusb_detach_kernel_driver` that will unload the driver if you have sufficient permission (root). On the Mac, [this is done with](https://github.com/libusb/libusb/wiki/FAQ#how-can-i-run-libusb-applications-under-mac-os-x-if-there-is-already-a-kernel-extension-installed-for-the-device-and-claim-exclusive-access) `kextunload` (also as root, in the terminal) but I do not recommend it one bit because it will attempt to unload the kernel driver for all devices, not just your device.  Aside from the fact that this will likely fail, I really don't see a situation where this would be appropriate. Deleting the driver from the system is an even worse solution. *If it is already claimed, then there is probably a method to communicate with it through the regular means of the system.*

However,  scientific equipment is usually defined as a *vendor-specific device* with a *vendor-specific protocol*, therefore the system will rarely match and we will be able to have access to the USB interface and communicate with the device through the various endpoints. That's what we will do next.

## Communicating with USB devices

We may know how to identify a device, configure it, pick an interface and select communication channels, but then what? What does it imply to "program a device" ? What does it mean to "program a 3D stage" ? We will start with the easiest devices (those with a few commands), and then move on to more complicated devices (with binary commands and multiple endpoints).

The basic idea when we program a device is to send a command that the device recognizes (`move to 10,0,0`), it will perform the requested task (actually move), and then will reply (`Ok`). For many devices, controlling the device is just a series of request/reply until you are done. The work is therefore to send the right data down the endpoints to the device, and interpret the replies the device is sending.

### Encoding the information

The information is encoded in bytes. The bytes have different meaning depending on what were are sending. A letter is a single byte (8 bits) that can take 256 values from 0 to 255, or in hexadecimal `0x00` to `0xff`.  ASCII encoding is standard for text: in that system, the letter 'A' is the number 65 (0x41), 'C' is 67 (0x43) etc... To write integer numbers larger than 255, we can put more than one byte together. For instance, if we put 2 bytes together, we can get 65,536 different values (from `0x0000` to `0xffff`), if we use 4 bytes together, we can write 4,294,967,296 different values (from `0x00000000` to `0xffffffff`). These integers have names in Python: 1 byte is called a `char`acter, 2 bytes is a `short int` and 4 bytes is a `long int`.  It is possible to interpret these as `signed` or `unsigned`, where `signed` is usually the default if nothing else is mentionned. The detailed difference between `signed` and `unsigned` is not critical here, as long as we use the appropriate type.  When we start with the least significant bytes then the most significant, we say the format is "little-endian", otherwise it is "big-endian". You can find a bit more information [here](https://github.com/dccote/Enseignement/blob/master/DAQ/Semaine-02.md).



# References

I have found various web sites over the years that may help you understand better, even though everything I wrote above is from experience accumulated over the years. Many web sites are either too detailed or too superficial. It is hard to find reasonable information, but I like the following:

1. "Beyond Logic", https://www.beyondlogic.org/usbnutshell/usb1.shtml.  Really complete, but may be too difficult.
2. "USB made simple", https://www.usbmadesimple.co.uk/index.html.  In the present document, I completely gloss over the fact that there is an Control endpoint #0 (IN/OUT).  All the "USB details" occur on those endpoints and it is not described in the USB Descriptors because it must be there and is not configurable. This document will give you more information to understand the nitty-gritty details if you are interested. (I myself have never learned these details, this is too low-level for me). This would be useful if you are making a USB chip.
3. "Pourquoi j'aime controler les appareils", https://github.com/dccote/Enseignement/blob/master/DAQ/Semaine-01.md
4. A small demo (in french) for serial communications with the FTDI chip: https://github.com/dccote/Enseignement/blob/master/DAQ/Semaine-02.md

**Post-scriptum**

Interesting: you made it this far.  If you want to discuss the possibility of an intership at some point in my group, send me an email with the subject "productId=stage", and tell me the vendorId of FTDI. Then we can talk.
