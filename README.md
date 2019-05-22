# PyHardwareLibrary
A simple device-oriented library with CommunicationPort for controlling devices

## Introduction
You will find a simple, trivial script named `cobolt.py` to change the power of the Cobolt laser. There are three versions: you should read the three examples :

1. `1-simple`: a very trivial implementation with simple commands in sequence
2. `2-class`: a class implementation of `CoboltLaser` that partially encapsulates the details and exposes a few functions: `setPower()` and `power()`
3. `3-class+debugPort`: a class implementation with a debug port that mimicks the real device

More to come.
