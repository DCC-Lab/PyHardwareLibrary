# Understanding RS-232 and its relation to USB

by Prof. Daniel Côté, Ph.D., P. Eng., dccote@cervo.ulaval.ca, http://www.dcclab.ca

You are here because you have an interest in programming hardware devices for scientific applications, and the communication with many of them is through the Universal Serial Bus, or USB. However, the ancestor of USB (the RS-232 serial port) sometimes shows its ugly head for reasons that will become obvious later, and understanding RS-232 becomes an important asset when dealing with some USB devices. This document will provide some background history and context to scientists who need to program USB devices. It is my perspective, with my superficial knowledge and my personal bias.

## Early expansion ports

Very quickly after the introduction of personal computers, it became clear that people wanted to interact with the outside world. The most important devices people wanted to connect were a printer and a modem. This required some means of communicating with a device external to the computer.  In the 80s, there were IBM PCs and Apple computers, but also a broad spectrum of more affordable computers like the Commodore-64, Amiga, Atari, ZX Spectrum, TRS-80. 

There were three issues that needed to be tackled: the physical connector (how things connect to the computer), the electrical assignment of the pins (what pin serves what purpose), and the software (what is said on these wires). These three things together will eventually define "a standard".

The way expansion was done at the time was mostly with an internal "slot", essentially a proprietary connector. The [Apple II](https://apple2history.org/history/ah13/#01) had an internal expansion slot that could be used for peripherals, the [Commodre 64](https://en.wikipedia.org/wiki/Commodore_64#Input/output_(I/O)_ports_and_power_supply) had a serial port that was a modified version of the IEEE-488 and a ROM expansion cartridge that could significantly expand the capabilities of the computer. [IBM PC's](https://en.wikipedia.org/wiki/IBM_Personal_Computer) had an internal ISA bus that also could accomodate various cards, including serial (RS-232) and parallel cards, and over time included an RS-232 port (a serial `COM` port) and what became IEEE 284 (a parallel `LPT` port). The Macintosh computer had RS-422 serial ports an a SCSI port.  As you can imagine, each manufacturer came up with their design, and purchasing an expansion card for one type of computer meant it would usually only work on that computer: the connectors were often different, and if they were not, the computer would also need to know what to say to the device (it needed to "support" that device with knowing what to say to make things happen). Sometimes, the connectors would be the same, but the pins would serve different purposes.  Today, a "connector" is mostly synomym with "a protocol", but that was not always the case. 

Eventually, [RS-232](https://en.wikipedia.org/wiki/RS-232) emerged as a standard for serial communication. Many, many different devices were designed, built and sold using the RS-232 standard as the communication method, and quoting the Wikipedia page of RS-232, we can already see where this is going:

> Nevertheless, thanks to their simplicity and past ubiquity, **RS-232 interfaces are still used**—particularly in industrial machines, networking equipment, and **scientific instruments** where a short-range, point-to-point, low-speed wired data connection is fully adequate.

Let's look at it in more details, since it looks like this RS-232 serial port will be relevant to us.

##The 'first' standard port: RS-232

The RS-232 serial port often uses a DB-9 connector that looks like this (obtained from the [commfront](https://www.commfront.com/pages/3-easy-steps-to-understand-and-control-your-rs232-devices)) with the following pin assignments:

<img src="README.assets/image-20210417140020797.png" alt="image-20210417140020797" style="zoom:50%;" />

The pins have different meaning if you are the computer (Data Terminal Equipment, DTE) or the device (Data Communication Equipment, or DCE): the transmit pin for one is obviously the receive pin for the other, etc.  I will discuss from the perspective of the computer (DTE), because this is also the way USB works, and we care about programming the computer, not the device.

We can certainly recognize the expected Receive and Transmit pins (Pin 2 RXD and Pin 3 TXD), but there are others that may need explanations. As mentionned before, the first uses of serial ports was for modems: we see this immediately with Pin 1 that is used to confirm that the phone line is active, and Pin 9 that indicates that the phone is ringing. The remaining pins are used to synchronize the computer with the peripheral: this is called hardware handshaking, or hardware flow control.

### Hardware flow control

The computer can request the permission to send data by asserting the Request to Send pin (RTS).  When the device is ready, it asserts (i.e. it raises the value to True, 1) the Clear To Send pin (CTS). In this situation, the device responds to request from the computer and **must** reply for the computer to start sending the data. The device can also request the permission to send data by asserting the Data Signal Ready (DSR) pin, and again, the computer **must** respond by asserting the Data Terminal Ready  (DTR) pin for the device to start sending the data.

The part that is important to us is that the computer and device **must agree on what they will do**, because this hardware handshake is optional: if the device expects that the computer will use the RTS pin to signal the availability of data, and that it will not transmit it until the CTS pin is asserted, then the computer better do that: if not, the RxD pin on the device will start blurting out data, but the device will not be ready to retrieve it.  Similarly, if the computer expects to get the permission from the device through the assertion of the CTS pin, then the device better do it, because if it does not, the computer will just wait forever for a signal that will never show up.  It is similar with the DSR and DTR pins. 

This "choice" (hardware handshake or not) is built into the device you have: if the device expects hardware flow control, the manual will tell you, and it will also tell you what type of hardware flow control you must perform.

### Software flow control

It is also possible to control the flow of data with special characters sent on the serial port, called XON and XOFF. This is not so critical to us and is rarely used, so I will not discuss it.  Obviously, if software flow control is expected, it needs to be managed at the software level (I never had to do that with any device I have ever progammed). This is quite rare because as soon as sometime other than text can be sent (binary numbers, raw spectrum data, anything non-text), then the possibility of getting "by chance" the code for XOFF is non-null and then the communication would come to a halt. This is really limited to communication protocols that rely solely on text.

### Speed and encoding

So, assuming we have dealt with hardware handshake properly, the Transmit pin and the Receive pin will start going from 0 to 1 and 1 to 0 to communicate information.  Assuming we are sending a command to the device, the computer will send, say, 0, then 0, 0, 0, 1, 1, 1, and finally 1 to send the values 0xf0, all on a single wire (TxD).  Since this is a single wire, this raises several questions:  

1. How fast will the transitions occur? The voltage will be up for 1 ms, then down for another 1 ms, etc...? The answer to this is the **baud rate, or speed**. There are lists of standard speeds, the most common being 9600 and 57600.
2. Then, how many bits will I send to form one 'character' ? As a reminder, the first modems in the 80s transmitted 300 bits per second. That is *millions* of times slower than our internet connections today.  Therefore, we could use only 7 bits instead of 8 bits and be 12.5% faster, because the US-ASCII characters can fit into 7 bits. This is the **data bit** choice  (8 or 7).
3. What if there is an error in transmission or reception? Electrical interferences occur, and errors are possible.  Is it possible to have at least some sort of error checking at a basic level? This is the purpose of the [**parity bit**](https://en.wikipedia.org/wiki/Parity_bit) (None, Even, Odd).
4. Finally, if I were to send several '1's in a row, the voltage will be high for several milliseconds.  If I were to send 1 million '1's, this would mean the voltge on the TxD pin would be high for 15 minutes (1000 seconds with 1ms per bit).  Chances are that the device may get lost or desynchronized. The answer to this are **stop bits**, that indicate the start and end of the character.

So when setting up an RS-232 connection, we need to determine all these parameters.  They are typically indicated by something like: [**9600/8:N:1**](https://en.wikipedia.org/wiki/8-N-1), for 9600 bits per second, 8 bits per character, no parity bit and 1 stop bit. Hardware or software flow control is indicated separately.  This information is indicated in the manual, and the speed is sometimes adjustable through various commands. There are tons of web sites with [details about this information](https://www.cmrr.umn.edu/~strupp/serial.html), but I will not go deeper here: we know these parameters must be set properly to communicate.

### The problems with RS-232

It should be obvious now what the problems can be: if the communication parameters are incorrect, no command will be understood, and no reply could be understood either. A [dialogue of the deaf](https://www.oxfordreference.com/view/10.1093/oi/authority.20110803095715819).

There is a second problem, less apparent than the first one but as important: even if I succeed in *setting up* the communication with the device, how do I know what is connected? Is it a printer? If it is, which printer? It's an HP printer? What model is it? Is it the same as last year's model? Has anything changed in the commands I can send? With RS-232, before you can confirm the identity of the device, you need to communicate with it by sending commands and understanding the replies.  This is quite wasteful: assuming that the communication is set up properly, you would need to send a command under the assumption that the device connected is the one you think it is, and if you do get a reply, it is probably the right device.  If you don't get a reply, you can assume it is probably not the right device. Then again, maybe the communication parameters were incorrect in the first place? Or the speed? Maybe the flow control? Is the documentation out of date? Who really knows? Countless hours in the lab have been lost by anyone who has ever programmed hardware devices because of this uncertainty (and as we will see below, this still occurs because RS-232 still lives behind the scene).

These are exactly the type of problems that USB was meant to solve.

## The transition from RS-232 to USB: FTDI comes to the rescue

When USB was introduced in 1996 and to the masses in 1998 with the iMac being the first computer dropping legacy ports, it was a revolution. USB was solving many problems we did not even know we had, but it made connectivity simpler: plug it in, start using it. That was nice. But then again, in the early years, there were very few USB devices (I remember the only affordable printer was an [Epson Stylus 740 printer](https://epson.ca/Support/Printers/Single-Function-Inkjet-Printers/Epson-Stylus-Series/Epson-Stylus-Color-740i/s/SPT_C257111)) and to say that some of them were buggy (or the drivers were buggy or the cables were buggy) may be an understatement. But still, it was refreshing.

Very quickly, chip manufacturers like FTDI provided a special chip that would take a USB connector and "translate it" into RS-232 with a DB-9 connector. These [USB-to-Serial adaptors](https://www.amazon.ca/USB-Serial-Adapter/s?k=USB+to+Serial+Adapter) from several vendors are still very popular, and most use the FTDI chip. It offered a quick solution to make RS-232 devices work on computers that were already leaving out the RS-232 ports (like the iMac for instance). The device manufacturers did not even have to do *anything*.

But eventually, device manufacturers had to update their devices to make them compatible.  FTDI offers again an attractive solution: a [USB chip that was pin-for-pin compatible](https://github.com/dccote/Enseignement/blob/master/DAQ/Semaine-02.md) with a standard RS-232 chip. It had a USB connector on one side and all the RS-232 pins on the other side. Many manufacturers used this: it meant they only had to replace a chip in their design and modify the enclosure to accomodate the USB connector, a *very* low-risk design change. On top of that, FTDI would provide a driver (for all platforms) that would expose the USB port as a "standard" serial port when it recognized it, and again, the manufacturers would not have to do much: they would essentially map the old RS-232 interface back onto the computer.  For a device manufacturer, this is nice. It is possible to do even better: simple tools allow the manufacturer to change the USB idVendor to its own id (after registering it) so this would mean that the device could be easily identifiable, and other information could be made available such as idProduct, serial number, manufacturer etc... But the market for scientific devices is small.  This means that the solution where the idVendor is unchanged was deemed sufficient by many manufacturers, because the devices would still work, and it meant no major investments in redesign, no need to register an idVendor with the USB consortium, no request to FTDI to include their idVendor in the list of supported vendors for their driver, and no driver code to write. So to this day, many USB devices appear as "FTDI chips", or idVendor 0x0403. When you [probe a USB device](README-USB.md) and see idVendor 0x0403, this means you will have to work a bit harder to get everything done, because it does not really tell you anything about the device: you only know that it is some device powered by a FTDI chip. Sometimes, but not consistently, the **iManufacturer** and **iProduct** string pointers are used to provide some information, but not always.  In addition, you (often, but not always) have to set the baud rate, data, stop and parity bits and, most importantly, the hardware flow control.  You are essentially back to square one, into RS-232 world, but with USB on top. Fun times.

## What next?

The next step if you are trying to work with RS-232 is to start using the standard serial port interface with a RS232-disguised-as-USB port on your computer.  I have written a document (in french only) that allows you to do just that.  It is called : ["DAQ: Entrées-sorties numériques avec le UM232R"](https://github.com/dccote/Enseignement/blob/09240b7b70b3b7b05646ea3af385adaa74f71b58/DAQ/Semaine-02.md). You require a FTDI UM232R chip to do it, but you can also just read the document.

## References

There are many web sites with information from where I gathered a coherent picture, but most of the information here comes from my own personal experience, aside from the exact names of all the standards (RS-422, ISA bus), connectors (DB9, DE9, etc...), specific introduction dates, and such that I obtained from Wikipedia.



Prof. Daniel Côté, Ph.D., P. Eng.

http://www.dcclab.ca

http://www.youtube.com/user/dccote

