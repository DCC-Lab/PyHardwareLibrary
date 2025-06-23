[TOC]

# Understanding USB cameras

USB cameras are everywhere, including built into our laptops. Most of the time, we don't even need to do anything for them to work in any software. How is this possible? This is because the USB standard includes not only a class ("here is a camera") but also a protocol for any computer to talk to such cameras since for the most part, they all do the same thing: capture an image and transfer it to the computer.  Let's dive a bit into these **USB Video Class Cameras** (UVC for short) to try to see how this fits in with the rest of our knowledge about USB.

## Motivation and plan

I needed to program my own USB Camera for a project.  In the process, I needed to figure out: why do I sometimes have to make it work myself (i.e. with a library or an external driver) and why does the computer sometimes recognize it by itself? Why do I sometimes need a driver or a library? Also, I have a [ZWO ASI183MM](https://astronomy-imaging-camera.com/product/asi183mm-pro-mono) Pro camera that I plan to use for a microscopy project. The web site mentionned : *["No driver installation needed on macOS"](https://astronomy-imaging-camera.com/software-drivers)*. I thought this was a sign that it  would work right away in all software, but that was not the case.  If I plug it in, it does not show up in Facetime or any other "regular software" like Quicktime Player.  So here I document my journey to help you (and me) understand USB cameras. 

## Finding USB cameras on my computer

First things first, let's list the available USB devices on my MacBook Pro 2019 with this script [we wrote before](README-USB.md). Since my computer has a USB WebCam and I am pluggin in the USB ZWO Camera, I expect two find two cameras, that should be simple. We run this:

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

We get two devices, one is not a camera. We see my ZWO Camera, but not my web cam: 

```shell
DEVICE ID 03c3:183e on Bus 000 Address 001 =================
 bLength                :   0x12 (18 bytes)
 bDescriptorType        :    0x1 Device
 bcdUSB                 :  0x300 USB 3.0
 bDeviceClass           :    0x0 Specified at interface           # Surprising: I expected a camera
 bDeviceSubClass        :    0x0
 bDeviceProtocol        :    0x0
 bMaxPacketSize0        :    0x9 (9 bytes)
 idVendor               : 0x03c3
 idProduct              : 0x183e
 bcdDevice              :    0x0 Device 0.0
 iManufacturer          :    0x1 ZWO                              # This is my Camera
 iProduct               :    0x2 ASI183MM Pro                     
 iSerialNumber          :    0x0 
 bNumConfigurations     :    0x1                                  # One configuration only: good
  CONFIGURATION 1: 128 mA ==================================
   bLength              :    0x9 (9 bytes)
   bDescriptorType      :    0x2 Configuration                    
   wTotalLength         :   0x1f (31 bytes)
   bNumInterfaces       :    0x1                                  # One interface.
   bConfigurationValue  :    0x1                                  # Configuration #1
   iConfiguration       :    0x0 
   bmAttributes         :   0x80 Bus Powered                      # I don't need an external power supply.
   bMaxPower            :   0x40 (128 mA)
    INTERFACE 0: Vendor Specific ===========================
     bLength            :    0x9 (9 bytes)
     bDescriptorType    :    0x4 Interface
     bInterfaceNumber   :    0x0
     bAlternateSetting  :    0x0
     bNumEndpoints      :    0x1
     bInterfaceClass    :   0xff Vendor Specific                  # Oops: vendor-specific interface, not
     bInterfaceSubClass :    0x0                                  # something like "Camera"
     bInterfaceProtocol :    0x0
     iInterface         :    0x0 
      ENDPOINT 0x81: Bulk IN ===============================      # Bulk IN, certainly to send data to
       bLength          :    0x7 (7 bytes)                        # computer. But where will I send my
       bDescriptorType  :    0x5 Endpoint                         # commands to configure the camera?
       bEndpointAddress :   0x81 IN
       bmAttributes     :    0x2 Bulk
       wMaxPacketSize   :  0x400 (1024 bytes)
       bInterval        :    0x0
```



The descriptors are commented.  Two things to notice:

1. The camera appears to identify its only interface as a `0xff` vendor-specific. Not looking good for general support.
2. The ZWO camera does not appear anywhere on my system (QuickTime device, Facetime, etc...). It is not recognized by the system.
3. We still don't see my Webcam on my 2019 MacBook Pro.



### Confirming the functionalities of the ZWO camera

For the camera to be recognized by the system, it needs, somewhere, to describe that it actually is a camera. After a bit of digging on the web, we find that the USB Video Class Desriptor (UVC) for short. The best documentation I have found [is here](https://www.xmos.ai/download/AN00127:-USB-Video-Class-Device(2.0.2rc1).pdf). It clearly says on page 8: 

> For Video class device, it is mandatory to set the ‘bDeviceClass’, ‘bDeviceSubClass’ and ‘bDeviceProtocol’ fields to 0xEF, 0x02 and 0x01 respectively.

In the USB descriptor, at the top level, we find these descriptors, but they are all `0x00`. 

```shell
 bDeviceClass           :    0x0 Specified at interface           # Surprising: I expected a camera
 bDeviceSubClass        :    0x0
 bDeviceProtocol        :    0x0
```

 This means that the device will provide the description in the interface instead. Let's look at the single interface defined: 

```python
     bInterfaceClass    :   0xff Vendor Specific                  # Oops: vendor-specific interface, not
     bInterfaceSubClass :    0x0                                  # something like "Camera"
     bInterfaceProtocol :    0x0
```

So clearly, my ZWO camera does not qualify as a USB Web Cam of type that could be recognized by the system because it is not described like as such in its USB descriptor.  That is ok, because ZWO provides a library and software to use the camera, so we willl have to go through that if we want to use it. 

### Accessing ASI ZWO Cameras from Python

This is an entire discussion in itself, but here are the steps to make it work:

1. We need to have the library from ASI, because it uses a proprietary communication protocol to talk the the camera (remember, `0xff` vendor-specific). The mac/linux version [is here](https://download.astronomy-imaging-camera.com/download/asi-camera-sdk-linux-mac/?wpdmdl=381).

   1. When you uncompress the file, you will find a library called: `libASICamera2.dylib`.
      <img src="README.assets/asiZwo.png" alt="ASIZwo" style="zoom:33%;" />

2. There is a [Python module for the ASI ZWO Cameras](https://pypi.org/project/zwoasi/) that will use the library from ASI and provide us with the necessary methods to access the camera and snap images. `pip install asizwo`

   1. To make it work, we need to tell the Python module where to get the library. This is done through a mechanism called environment variables. We then need to set the path to that library in a variable called `ZWO_ASI_LIB`:

      ```shell
      ZWO_ASI_LIB="/Users/dccote/Downloads/ASI_linux_mac_SDK_V1.17/lib/mac/libASICamera2.dylib"; export ZWO_ASI_LIB
      ```

   2. If you run the [example](https://github.com/stevemarple/python-zwoasi/blob/master/zwoasi/examples/zwoasi_demo.py) code `zwoasi_demo.py` from the [GitHub repository](https://github.com/stevemarple/python-zwoasi/tree/master/zwoasi/examples), on macOS, you will get a warning that the library was blocked because it is from an unidentified developer.  This is unfortunate: libraries that are not "signed" by a security certificate get blocked on macOS.  Obviously, ASI did not pay the 99$ to get a Developer ID from Apple.

   3. You need to go to the Security System Preferences and "Allow" libASICamera2.dylib to run even if it is an unsigned library.

3. After that, you can look at [the example code](https://github.com/stevemarple/python-zwoasi/blob/master/zwoasi/examples/zwoasi_demo.py) to see how to get images from this great camera, affordable camera. That said, since not everyone has a ZWO camera, we will focus on our USB Webcam.

4. As an aside for `asizwo`, the best option would be that the library would be signed,  it would be installed in `/usr/local/lib`, and the `asizwo` Python module would look it up there because it is a standard location. I may help the zwoasi module writer for that. We can temporarily attempt something like that:

   ```sh
   Desktop % cp ~/ASI_linux_mac_SDK_V1.17/lib/mac/libASICamera2* /usr/local/lib/
   Desktop % cp ~/ASI_linux_mac_SDK_V1.17/include/ASICamera2.h /usr/local/include/
   ```

   And we modify the code for future references to use `find_library`, a standard function in Python to find libraries, as:

   ```python
   from ctypes.util import find_library
   
   [...]
   
   # Initialize zwoasi with the name of the SDK library
   if args.filename:
       asi.init(args.filename)
   elif env_filename:
       asi.init(env_filename)
   else:
       pathToLib = find_library("ASICamera2")
       if pathToLib is not None:
           asi.init(pathToLib)
       else:
           print('The filename of the SDK library is required (or set ZWO_ASI_LIB environment variable with the filename)')
           sys.exit(1)
   
   ```

   

### Finding my Macbook web cam

The recent Macbook Pro has a T2-security chip that adds a layer of security so that hackers cannot sneak in and watch your camera.  However, PyUSB is not able to list the devices on that Secure USB bus apparently.  On Windows however, this works fine, so I suspect Parallels Desktop remaps the T2 bus to a regular bus that PyUSB can read, but [I will investigate later](https://stackoverflow.com/questions/67201458/not-seeing-all-usb-devices-with-pyusb-and-libusb-on-t2-macbook-pro).  Here I see many devices, but most importantly I can see my WebCam:

```shell
DEVICE ID 203a:fff9 on Bus 002 Address 001 =================
 bLength                :   0x12 (18 bytes)
 bDescriptorType        :    0x1 Device
 bcdUSB                 :  0x310 USB 3.1
 bDeviceClass           :   0xef Miscellaneous                # The class for a Video camera when
 bDeviceSubClass        :    0x2                              # Subclass 2, protocol 1 is given.
 bDeviceProtocol        :    0x1
 bMaxPacketSize0        :    0x9 (9 bytes)
 idVendor               : 0x203a
 idProduct              : 0xfff9

[...]
    INTERFACE 1: Video =====================================
     bLength            :    0x9 (9 bytes)
     bDescriptorType    :    0x4 Interface
     bInterfaceNumber   :    0x1
     bAlternateSetting  :    0x0
     bNumEndpoints      :    0x1
     bInterfaceClass    :    0xe Video                         # Alright: looking good, Video device
     bInterfaceSubClass :    0x2                               # some subclass with protocol 0
     bInterfaceProtocol :    0x0
     iInterface         :    0x6 Error Accessing String
      ENDPOINT 0x83: Bulk IN ===============================
       bLength          :    0x7 (7 bytes)
       bDescriptorType  :    0x5 Endpoint                      # An endpoint to send data
       bEndpointAddress :   0x83 IN
       bmAttributes     :    0x2 Bulk
       wMaxPacketSize   :  0x400 (1024 bytes)
       bInterval        :    0x0
```

So I may not be able to see it directly with PyUSB on my Mac for some reason, but nevertheless, if I use Parallels Desktop to lookup my camera on Windows, I clearly see that my Webcam fits the description of a generic USB camera (or UVC) because  `bDeviceClass`, `bDeviceSubClass` and `bDeviceProtocol` fields are set properly. I am not sure why that is the case, but it does not matter, we can have a solution: OpenCV or Open Computer Vision library, which we will look at below.

## Programming a UVC ourselves?

We could be optimistic that we could program the UVC camera ourselves.  In that case, we would read the documentation for the standard, and call everything with PyUSB (which itself goes through libusb). There are many reasons why this is not a good idea:

1. First, let's not forget that the operating system will take over the device because it will recognize it.  When we try to communicate through a USB Endpoint, this will likely fail (not sure, should try it) because the operating system will have control of the USB Device. If we really wanted to start programming it, we would need to find a find for the device to not be recognized by the system. This is discussed [elsewhere](README-USB.md) how this is a bad idea.
2. Second, the UVC standard is complicated. Again, take a look at [this](https://www.xmos.ai/download/AN00127:-USB-Video-Class-Device(2.0.2rc1).pdf) to see all the calls that we would need to implement. This looks like a lot of work.
3. Third, really, it is the whole purpose of standard devices to be managed at the system level, so let's not try to redo what has been done already. 

## OpenCV to manage UVC devices

OpenCV is a really good (although sometimes intimidating) software library because it provides basic video capture and file loading, many many basic operations but also many very complex image manipulation functions (image segmentation, face recognition, tracking). If we install OpenCV2 (instructions elsewhere), then we can run the following Python script to display images with our camera:

```python
import cv2 

# Open the first camera we find
cap = cv2.VideoCapture(0)
#Check whether user selected camera is opened successfully.
if not (cap.isOpened()):
    print("Could not open video device")
    exit(1)

while(True):
    # Capture frame-by-frame
    ret, frame = cap.read()
    # Display the resulting frame
    cv2.imshow('preview',frame)
    #Waits for a user input to quit the application
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()
```

We get a window with a video until we press `q`:

<img src="README.assets/preview.png" alt="image-20210421121518002" style="zoom:25%;" />



# Camera as a PhysicalDevice

Finally, to include camera support to our HardwareLibrary, we simply need to create a `CameraDevice` that inherits from `PhysicalDevice`, and then a specific `OpenCVCameraDevice` with the specifics of OpenCV. To support other cameras (such as the ZWO), we will create a ZWOCameraDevice and overload the specifics `doInitializeDevice`, `doShutdownDevice` and `doCaptureFrame`.

```python
import time
from enum import Enum
from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from threading import Thread, RLock
import cv2
import re

class CameraDeviceNotification(Enum):
    willStartCapture    = "willStartCapture"
    didStartCapture     = "didStartCapture"
    willStopCapture     = "willStopCapture"
    didStopCapture      = "didStopCapture"
    imageCaptured       = "imageCaptured"

class CameraDevice(PhysicalDevice):
    def __init__(self, serialNumber:str = None, idProduct:int = None, idVendor:int = None):
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""
        self.quitLoop = False
        self.lock = RLock()
        self.mainLoop = None

    def doShutdownDevice(self):
        with self.lock:
            if self.isCapturing:
                self.stop()

    def livePreview(self):
        NotificationCenter().postNotification(notificationName=\          CameraDeviceNotification.willStartCapture, notifyingObject=self)
        self.captureLoopSynchronous()

    def start(self):
        with self.lock:
            if not self.isCapturing:
                self.quitLoop = False
                self.mainLoop = Thread(target=self.captureLoop, name="Camera-CaptureLoop")
                NotificationCenter().postNotification(notificationName=CameraDeviceNotification.willStartCapture, notifyingObject=self)
                self.mainLoop.start()
            else:
                raise RuntimeError("Capture loop already running")

    @property
    def isCapturing(self):
        return self.mainLoop is not None

    def stop(self):
        if self.isCapturing:
            NotificationCenter().postNotification(CameraDeviceNotification.willStopCapture, notifyingObject=self)
            with self.lock:
                self.quitLoop = True
            self.mainLoop.join()
            self.mainLoop = None
            NotificationCenter().postNotification(CameraDeviceNotification.didStopCapture, notifyingObject=self)
        else:
            raise RuntimeError("No monitoring loop running")

    def captureLoopSynchronous(self):
        frame = None
        NotificationCenter().postNotification(notificationName=CameraDeviceNotification.didStartCapture,
                                              notifyingObject=self)
        while (True):
            frame = self.doCaptureFrame()
            NotificationCenter().postNotification(CameraDeviceNotification.imageCaptured, self, frame)

            cv2.imshow('Preview (Q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                NotificationCenter().postNotification(CameraDeviceNotification.willStopCapture, notifyingObject=self)
                break

        cv2.destroyAllWindows()
        NotificationCenter().postNotification(CameraDeviceNotification.didStopCapture, notifyingObject=self)

    def captureFrames(self, n=1):
        frames = []
        for i in range(n):
            frames.append(self.doCaptureFrame())
        return frames

    def captureLoopThread(self):
        frame = None
        NotificationCenter().postNotification(notificationName=CameraDeviceNotification.didStartCapture,
                                              notifyingObject=self)
        while (True):
            frame = self.doCaptureFrame()
            NotificationCenter().postNotification(CameraDeviceNotification.imageCaptured, self, frame)

            if self.quitLoop:
                return

class OpenCVCamera(CameraDevice):

    def __init__(self, serialNumber:str = None, idProduct:int = None, idVendor:int = None):
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""
        self.cameraHandler = None
        self.cvCameraIndex = 0
        if serialNumber is not None:
            self.cvCameraIndex = int(serialNumber)

    def openCVProperties(self):
        properties = {}
        for property in dir(cv2):
            if re.search('CAP_', property) is not None:
                indexProp = getattr(cv2, property)
                value = cam.get(indexProp)
                if value != 0:
                    properties[property] = value
        return properties

    @classmethod
    def isCompatibleWith(cls, serialNumber, idProduct, idVendor):
        cameraIndex = int(serialNumber)

        cam = cv2.VideoCapture(cameraIndex)
        wasAcquired, frame = cam.read()
        cam.release()

        return True

    def doInitializeDevice(self):
        with self.lock:
            # FIXME: Open the first camera we find
            self.cameraHandler = cv2.VideoCapture(self.cvCameraIndex)

            if self.cameraHandler is None:
                raise Exception("Could not open video device")

            if not (self.cameraHandler.isOpened()):
                raise Exception("Could not open video device")

    def doShutdownDevice(self):
        super().doShutdownDevice()
        with self.lock:
            self.cameraHandler.release()
            self.cameraHandler = None

    def doCaptureFrame(self):
        with self.lock:
            # Capture frame-by-frame
            ret, frame = self.cameraHandler.read()
            return frame

    @classmethod
    def availableCameras(cls):
        numberOfCameras = 0
        for i in range(10):
            cam = cv2.VideoCapture(i)
            wasAcquired, frame = cam.read()
            cam.release()

            if not wasAcquired:
                break

            numberOfCameras += 1

        return numberOfCameras

if __name__ == "__main__":
    print(OpenCVCamera.availableCameras())
    cam = OpenCVCamera(serialNumber="1")
    cam.initializeDevice()
    cam.livePreview()
    cam.shutdownDevice()

```

