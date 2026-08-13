"""The abstract base every device in the library is built on.

PhysicalDevice owns what is the same for all hardware -- identity, the connection
lifecycle and its state machine, the port handle, notifications, and the background
status thread -- so a driver writes only the bytes its instrument expects.
"""

from abc import ABC, abstractmethod
from enum import Enum, IntEnum
from threading import Thread, RLock

from hardwarelibrary import utils
from hardwarelibrary.capabilities import Capability
from notificationcenter import NotificationCenter
import typing
import time
import re


debugClassIdVendor = 0xffff # My special vendorId for debug classes

class DeviceState(IntEnum):
    """Where a device is in its connection lifecycle.

    A device starts Unconfigured, becomes Ready when initializeDevice() succeeds,
    and returns to Recognized on shutdown: known to work, but currently closed.
    Unrecognized means initialization was attempted and failed.
    """

    Unconfigured = 0 # Dont know anything
    Ready = 1        # Connected and initialized
    Recognized = 2   # Initialization has succeeded, but currently shutdown
    Unrecognized = 3 # Initialization failed

class PhysicalDeviceNotification(Enum):
    """What every device announces about its own lifecycle.

    The did* notifications are posted whether the operation succeeded or not,
    carrying the exception as their user_info when it failed. `status` is posted
    by the background thread at every refreshInterval, carrying whatever
    doGetStatusUserInfo() returns.
    """

    willInitializeDevice       = "willInitializeDevice"
    didInitializeDevice        = "didInitializeDevice"
    willShutdownDevice         = "willShutdownDevice"
    didShutdownDevice          = "didShutdownDevice"
    status                     = "status"

class PhysicalDevice(ABC):
    """Abstract base for every device the library supports.

    A driver subclasses this -- usually through its family base, and alongside the
    capability mixins it supports -- and implements doInitializeDevice and
    doShutdownDevice. Forgetting either raises TypeError at instantiation rather
    than at call time.

    A device is identified by a USB vendor/product pair and a serial number. The
    class attributes classIdVendor and classIdProduct declare what a driver binds
    to, and an instance may narrow that with its own serialNumber. An instrument
    reached through a generic USB/RS-232 converter has no identity of its own and
    sets usesGenericSerialConverter, which changes how it is matched (see vidpids).

    Public methods here are concrete and delegate to do* hooks, the pattern the
    whole library follows: the public side owns state, validation and
    notifications, so none of that has to be repeated in a driver.
    """

    class UnableToInitialize(Exception):
        """doInitializeDevice failed. The driver's own exception is wrapped in
        this one's args, so the true cause stays readable."""

    class UnableToShutdown(Exception):
        """doShutdownDevice failed, wrapping the driver's exception the same way."""

    class ClassIncompatibleWithRequestedDevice(Exception):
        """The requested idVendor/idProduct is not one this driver class binds to."""

    class NotInitialized(Exception):
        """An operation was attempted on a device that is not Ready. Raised by
        validateReady(), which guards every operation the capabilities expose."""

    classIdVendor = None
    classIdProduct = None
    commands = None

    # The CommandDictionary this driver speaks, for performTransaction below.
    # None until a driver sets it, which is every driver still using the older
    # commands dict above. SutterDevice is the first to set it.
    protocol = None

    # True when classIdVendor/classIdProduct are those of a generic, off-the-shelf
    # USB/RS-232 converter (a stock FTDI/Prolific/CP210x/CH34x cable) rather than
    # the instrument's own identity. Such a device shares its VID/PID with every
    # other instrument behind the same cable model, so it cannot be identified by
    # VID/PID alone: it matches any generic converter (see vidpids) and must be
    # disambiguated by serial number, and DeviceManager will not auto-probe it.
    usesGenericSerialConverter = False

    def __init__(self, serialNumber:str, idProduct:int, idVendor:int):
        """Bind this instance to one device, without opening anything.

        A serialNumber of "*" or None becomes the regex ".*", so both spellings
        mean "the first one found"; any other value is matched as a pattern.
        idProduct and idVendor fall back to the class attributes when None, which
        is why most drivers are constructed with no arguments at all. The pair must
        be one this class binds to, or ClassIncompatibleWithRequestedDevice is
        raised.

        The device is left Unconfigured: no port is opened until initializeDevice().
        """
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

        # Cooperative base: forward to the rest of the MRO so capability mixins
        # mixed in alongside a device (e.g. WavelengthCalibrationCapability) get their
        # own __init__ run. The device-identity arguments are consumed here, so
        # nothing is forwarded; a mixin __init__ must therefore take no required
        # arguments and call super().__init__() itself.
        super().__init__()

    def validateReady(self, operation=None):
        """Raise PhysicalDevice.NotInitialized unless the device is Ready.

        Overrides the no-op on Capability, which sits behind PhysicalDevice in a
        driver's MRO, so every notified operation is guarded without a driver
        writing anything. Without it, an operation on an unopened device fails
        deep inside the driver on a port that is still None -- or worse, a debug
        device answers as though the hardware had done it.
        """
        if self.state != DeviceState.Ready:
            raise PhysicalDevice.NotInitialized(
                "Cannot {0} on {1}: the device is {2}, not Ready. Call "
                "initializeDevice() first.".format(
                    "{0}()".format(operation) if operation else "operate",
                    type(self).__name__, self.state.name))

    def capabilities(self) -> list:
        """Returns the capability mixins this device supports, as classes.

        Walks the MRO for Capability subclasses, which is why a driver gets this
        for free by declaring the mixins it implements. Use hasCapability() to ask
        about one, and allCapabilities() in capabilities.py for what the library
        can express at all.
        """
        # The capability mixins, not the Capability marker nor the device class
        # itself (a driver is a Capability subclass too, but it is a
        # PhysicalDevice).
        return [klass for klass in type(self).__mro__
                if issubclass(klass, Capability)
                and klass is not Capability
                and not issubclass(klass, PhysicalDevice)]

    def hasCapability(self, capabilityClass) -> bool:
        """True when this device supports capabilityClass, e.g. ShutterCapability.

        Lets a caller adapt to whatever is on the bench rather than hard-coding one
        model: `if laser.hasCapability(ShutterCapability): laser.closeShutter()`.
        """
        return isinstance(self, capabilityClass)

    @classmethod
    def vidpids(cls):
        """Returns the (idVendor, idProduct) pairs this class binds to.

        Normally the single pair declared by classIdVendor/classIdProduct. An
        instrument behind a generic converter matches every generic converter
        vendor instead, with the product wildcarded to None, since its USB identity
        is the cable's rather than its own.
        """
        if cls.usesGenericSerialConverter:
            # Identity is not in the VID/PID: match any generic converter chip,
            # PID wildcarded (None). Local import avoids a physicaldevice <->
            # communication import cycle.
            from hardwarelibrary.communication.serialport import SerialPort
            return [(idVendor, None) for idVendor in SerialPort.genericSerialConverterVendors]
        return [(cls.classIdVendor, cls.classIdProduct)]

    @classmethod
    def isCompatibleWith(cls, serialNumber, idProduct, idVendor):
        """True when this class binds to the given idVendor/idProduct.

        A None product in a vidpids pair is a wildcard matching any product from
        that vendor. serialNumber is accepted for symmetry with the callers but
        takes no part in the decision: a serial number tells two identical
        instruments apart, not two driver classes.
        """
        for compatibleIdVendor, compatibleIdProduct in cls.vidpids():
            if idVendor == compatibleIdVendor:
                # A None product id in the pair is a wildcard: it matches any
                # product behind that vendor (used for generic converters).
                if compatibleIdProduct is None or idProduct == compatibleIdProduct:
                    return True

        return False

    @classmethod
    def commandHelp(cls):
        """Print the commands table of this class, if it has one.

        Only the few devices using the table-driven `commands` pattern have
        anything to show; every other driver reports that no help is available.
        """
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

    @classmethod
    def isDebugClass(cls):
        """True for the debug drivers, which carry the reserved vendor id 0xFFFF
        so that discovery can leave them out of a search for real hardware."""
        return cls.classIdVendor == debugClassIdVendor

    @classmethod
    def isAbstractClass(cls):
        """True when the class declares no USB identity, which marks a family base
        rather than a driver that can be instantiated against hardware."""
        return (cls.classIdVendor == None) or (cls.classIdProduct == None)

    def initializeDevice(self):
        """Open the device and bring it to Ready, unless it already is.

        Posts willInitializeDevice, runs the driver's doInitializeDevice, then
        posts didInitializeDevice. On failure the state becomes Unrecognized, the
        did notification is posted anyway with the exception as its user_info, and
        the driver's exception is wrapped in UnableToInitialize -- wrapped rather
        than replaced, so the true cause stays readable in its args.
        """
        if self.state != DeviceState.Ready:
            try:
                NotificationCenter().post_notification(PhysicalDeviceNotification.willInitializeDevice, notifying_object=self)
                self.doInitializeDevice()
                self.state = DeviceState.Ready
                NotificationCenter().post_notification(PhysicalDeviceNotification.didInitializeDevice, notifying_object=self)
            except Exception as error:
                self.state = DeviceState.Unrecognized
                NotificationCenter().post_notification(PhysicalDeviceNotification.didInitializeDevice, notifying_object=self, user_info=error)
                raise PhysicalDevice.UnableToInitialize(error)

    @abstractmethod
    def doInitializeDevice(self):
        """Open the port and configure the instrument. Written by the driver.

        Keep it minimal: the state machine, notifications and error wrapping are
        initializeDevice()'s business. Raise on failure; do not swallow.
        """
        ...

    def initializeIfNeeded(self):
        """Initialize a device that has never been opened, and do nothing otherwise.

        Note that a device which has been shut down is Recognized, not
        Unconfigured, so this will not reopen one; call initializeDevice() for that.
        """
        if self.state == DeviceState.Unconfigured:
            self.initializeDevice()

    def shutdownDevice(self):
        """Close the device and leave it Recognized, if it is Ready.

        Stops the background status thread first, then runs the driver's
        doShutdownDevice between willShutdownDevice and didShutdownDevice. The
        state is set and the port closed whatever happens, so a driver that raises
        on the way down still leaves a device that can be reopened; its exception
        is wrapped in UnableToShutdown.
        """
        if self.state == DeviceState.Ready:
            try:
                NotificationCenter().post_notification(PhysicalDeviceNotification.willShutdownDevice, notifying_object=self)
                if self.isMonitoring:
                    self.stopBackgroundStatusUpdates()

                self.doShutdownDevice()
                NotificationCenter().post_notification(PhysicalDeviceNotification.didShutdownDevice, notifying_object=self)
            except Exception as error:
                NotificationCenter().post_notification(PhysicalDeviceNotification.didShutdownDevice, notifying_object=self, user_info=error)
                raise PhysicalDevice.UnableToShutdown(error)
            finally:
                self.state = DeviceState.Recognized
                if self.port is not None:
                    self.port.close()
                    self.port = None

    @abstractmethod
    def doShutdownDevice(self):
        """Release the instrument. Written by the driver.

        Keep it minimal, as with doInitializeDevice: closing self.port is
        shutdownDevice()'s business, not the driver's.
        """
        ...

    def startBackgroundStatusUpdates(self):
        """Start the thread that posts a status notification every refreshInterval.

        Raises RuntimeError when one is already running; ask isMonitoring first.
        """
        with self.lock:
            if not self.isMonitoring:
                self.quitMonitoring = False
                self.monitoring = Thread(target=self.backgroundStatusUpdates, name="Physical-Device-backgroundStatusUpdates")
                self.monitoring.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    def backgroundStatusUpdates(self):
        """The monitoring thread's loop: post the status, then wait, until asked to stop.

        The stop request is only read after a post, so one notification always goes
        out and stopBackgroundStatusUpdates() returns at the end of the current
        cycle rather than immediately.
        """
        while True:
            user_info = self.doGetStatusUserInfo()

            NotificationCenter().post_notification(PhysicalDeviceNotification.status, notifying_object=self,
                                                  user_info=user_info)

            with self.lock:
                if self.quitMonitoring:
                    break
            time.sleep(self.refreshInterval)

    def doGetStatusUserInfo(self):
        """What the periodic status notification carries. None by default.

        Optional: a driver overrides it with whatever is worth watching, the way a
        power meter reports its latest reading.
        """
        return None

    @property
    def isMonitoring(self):
        """True while the background status thread is running."""
        with self.lock:
            return self.monitoring is not None

    def stopBackgroundStatusUpdates(self):
        """Ask the monitoring thread to stop and wait for it to finish.

        Raises RuntimeError when none is running. Called for you by
        shutdownDevice(), so a closed device never leaves a thread behind.
        """
        if self.isMonitoring:
            with self.lock:
                self.quitMonitoring = True
            self.monitoring.join()
            self.monitoring = None
        else:
            raise RuntimeError("No status loop running")

    def performTransaction(self, name, **arguments) -> dict:
        """Perform one command of self.protocol once, and return what came back.

        A Command says what an exchange is; this carries it out. The description
        supplies the bytes to write and says how to read the answer, so a driver
        that sets protocol needs no send-and-receive code of its own: it calls
        this by name and gets a dict.

        How much to read is the reply's own business. A binary reply gives its
        readLength, since a fixed-size frame has no terminator to stop at; a text
        reply gives None, and the port reads up to its own terminator instead.
        Both go through the primitives of CommunicationPort and nothing else.

        The write and the read are held together under the port's
        transactionLock, so a concurrent caller cannot slip a command in between
        and be handed this one's reply. Both locks are reentrant, so the port
        taking portLock inside each primitive costs nothing here.

        This does not require the device to be Ready. A driver needs it inside
        doInitializeDevice, to confirm the instrument answers before the state can
        become Ready, and readiness is in any case the business of the public
        methods that validateReady guards -- not of the wire. The sendCommand this
        replaces did check, which is exactly why SutterDevice had to reach around
        it during initialization.

        Args:
            name: the command to perform, one of the names in self.protocol
            **arguments: the values the command carries, passed by name

        Returns:
            What the reply carried, as {field name: value}. Empty for a command
            the instrument does not answer, and for one whose whole answer is a
            fixed acknowledgement the description already states.

        Raises:
            NotImplementedError: when this driver has no protocol, which means it
                either still uses the commands dict or has nothing to speak with.
            KeyError: when no command goes by that name, listing the ones that do.
            ReplyDidNotMatch: when the instrument answers something the
                description does not allow, naming the command.
        """
        if self.protocol is None:
            raise NotImplementedError(
                "{0} has no protocol to perform {1!r} with".format(
                    type(self).__name__, name))

        command = self.protocol[name]
        with self.port.transactionLock:
            self.port.writeData(command.encode(**arguments))
            if not command.expectsReply:
                return {}
            if command.reply.readLength is None:
                return command.decode(self.port.readString())
            return command.decode(self.port.readData(command.reply.readLength))

    @classmethod
    def any(cls):
        """Incomplete: enumerates, discards the result, and returns None.

        Intended to return the first connected device of this class or any of its
        subclasses, ready to use. Spectrometer.any() overrides it with a working
        implementation, which is why nothing has noticed. Two things block the
        generic version: getAllUSBIds walks subclasses only, so a leaf driver such
        as SutterDevice searches an empty list, and only modules that have been
        imported are visible to that walk.
        """
        vidpids = utils.getAllUSBIds(cls)
        utils.connectedUSBDevices(vidpids)

    @classmethod
    def connectedDevices(cls, vidpids = None, serialNumberPattern=None):
        """Returns an (idVendor, idProduct, candidateClasses) triple per device found.

        Searches the USB identities of this class's subclasses, or the vidpids
        given. candidateClasses is a list because it can hold more than one driver:
        four of them share the stock FTDI 0x0403:0x6001, so an identity match alone
        cannot say which instrument is on the other end.

        Prints its intermediate results; that is debugging left in place.
        """
        if vidpids is None:
            vidpids = utils.getAllUSBIds(cls)
        usbDevices = utils.connectedUSBDevices(vidpids=vidpids, serialNumberPattern=serialNumberPattern)
        print(vidpids)
        print(usbDevices)

        devices = []
        for usbDevice in usbDevices:
            possibleClasses = utils.getCandidateDeviceClasses(cls, usbDevice.idVendor, usbDevice.idProduct)
            devices.append( (usbDevice.idVendor, usbDevice.idProduct, possibleClasses) )

        return devices

    @classmethod
    def uniqueDevice(cls, vidpids=None, serialNumberPattern=None):
        """Not implemented: returns None.

        Intended to return the one connected device of this class, raising when
        none or several match, so that a script can state that it expects exactly
        one instrument.
        """

    @classmethod
    def anyDevice(cls, vidpids=None, serialNumberPattern=None):
        """Incomplete, and a duplicate of any(): enumerates, discards, returns None.

        One of the two should go when discovery is written properly.
        """
        vidpids = utils.getAllUSBIds(cls)
        utils.connectedUSBDevices(vidpids)
