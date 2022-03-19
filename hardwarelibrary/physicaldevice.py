from enum import Enum, IntEnum
from threading import Thread, RLock
from hardwarelibrary.notificationcenter import NotificationCenter
import typing
import time
import re

class DeviceState(IntEnum):
    Unconfigured = 0 # Dont know anything
    Ready = 1        # Connected and initialized
    Recognized = 2   # Initialization has succeeded, but currently shutdown
    Unrecognized = 3 # Initialization failed

class PhysicalDeviceNotification(Enum):
    willInitializeDevice       = "willInitializeDevice"
    didInitializeDevice        = "didInitializeDevice"
    willShutdownDevice         = "willShutdownDevice"
    didShutdownDevice          = "didShutdownDevice"
    status                     = "status"

class PhysicalDevice:
    class UnableToInitialize(Exception):
        pass
    class UnableToShutdown(Exception):
        pass
    class ClassIncompatibleWithRequestedDevice(Exception):
        pass
    class NotInitialized(Exception):
        pass

    classIdVendor = None
    classIdProduct = None
    commands = None

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        if serialNumber == "*" or serialNumber is None:
            serialNumber = ".*"
        if idProduct is None:
            idProduct = self.classIdProduct
        if idVendor is None:
            idVendor = self.classIdVendor

        if not self.isCompatibleWith(serialNumber, idProduct, idVendor):
            raise PhysicalDevice.ClassIncompatibleWithRequestedDevice("You must define classIdVendor classIdProduct")

        self.idVendor = idVendor
        self.idProduct = idProduct
        self.serialNumber = serialNumber
        self.state = DeviceState.Unconfigured

        # So far, everything is USB, let's just assume they all need this:
        self.usbDevice = None
        self.port = None

        self.lock = RLock()
        self.quitMonitoring = False
        self.monitoring = None
        self.refreshInterval = 1.0

    @classmethod
    def candidates(cls, idVendor, idProduct):
        candidateClasses = []
        
        if cls.isCompatibleWith(serialNumber="*", idProduct=idProduct, idVendor=idVendor):
            candidateClasses.append(cls) 

        for aSubclass in cls.__subclasses__():
            candidateClasses.extend(aSubclass.candidates(idVendor, idProduct))

        return candidateClasses

    @classmethod
    def isCompatibleWith(cls, serialNumber, idProduct, idVendor):
        if idVendor == cls.classIdVendor and idProduct == cls.classIdProduct:
            return True

        return False

    @classmethod
    def commandHelp(cls):
        className = "{0}".format(cls)
        match = re.search(r".*?\.(\w*?)'>", className)
        if match is not None:
            className = match.groups(1)[0]

        if cls.commands is None:
            print("No help available for {0}".format(className))
            return

        print("Help for {0}".format(className))
        for name, command in cls.commands.items():
            if command.numberOfArguments > 0:
                print("'{0}' followed by {3} args in format {2} [{1}]".format(name, command.payload, match.groups(), command.numberOfArguments))
            else:
                print("'{0}' [{1}]".format(name, command.payload))

    def initializeDevice(self):
        if self.state != DeviceState.Ready:
            try:
                NotificationCenter().postNotification(PhysicalDeviceNotification.willInitializeDevice, notifyingObject=self)
                self.doInitializeDevice()
                self.state = DeviceState.Ready
                NotificationCenter().postNotification(PhysicalDeviceNotification.didInitializeDevice, notifyingObject=self)
            except Exception as error:
                self.state = DeviceState.Unrecognized
                NotificationCenter().postNotification(PhysicalDeviceNotification.didInitializeDevice, notifyingObject=self, userInfo=error)
                raise PhysicalDevice.UnableToInitialize(error)

    def doInitializeDevice(self):
        raise NotImplementedError("Base class must override doInitializeDevice()")

    def initializeIfNeeded(self):
        if self.state == DeviceState.Unconfigured:
            self.initializeDevice()

    def shutdownDevice(self):
        if self.state == DeviceState.Ready:
            try:
                NotificationCenter().postNotification(PhysicalDeviceNotification.willShutdownDevice, notifyingObject=self)
                if self.isMonitoring:
                    self.stopBackgroundStatusUpdates()

                self.doShutdownDevice()
                NotificationCenter().postNotification(PhysicalDeviceNotification.didShutdownDevice, notifyingObject=self)
            except Exception as error:
                NotificationCenter().postNotification(PhysicalDeviceNotification.didShutdownDevice, notifyingObject=self, userInfo=error)
                raise PhysicalDevice.UnableToShutdown(error)
            finally:
                self.state = DeviceState.Recognized
                if self.port is not None:
                    self.port.close()
                    self.port = None

    def doShutdownDevice(self):
        raise NotImplementedError("Base class must override doShutdownDevice()")

    def startBackgroundStatusUpdates(self):
        with self.lock:
            if not self.isMonitoring:
                self.quitMonitoring = False
                self.monitoring = Thread(target=self.backgroundStatusUpdates, name="Physical-Device-backgroundStatusUpdates")
                self.monitoring.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    def backgroundStatusUpdates(self):
        while True:
            userInfo = self.doGetStatusUserInfo()

            NotificationCenter().postNotification(PhysicalDeviceNotification.status, notifyingObject=self,
                                                  userInfo=userInfo)

            with self.lock:
                if self.quitMonitoring:
                    break
            time.sleep(self.refreshInterval)

    def doGetStatusUserInfo(self):
        return None

    @property
    def isMonitoring(self):
        with self.lock:
            return self.monitoring is not None

    def stopBackgroundStatusUpdates(self):
        if self.isMonitoring:
            with self.lock:
                self.quitMonitoring = True
            self.monitoring.join()
            self.monitoring = None
        else:
            raise RuntimeError("No status loop running")

    def sendCommand(self, command):
        if self.state != DeviceState.Ready:
            raise PhysicalDevice.NotInitialized

        command.send(port=self.port)
