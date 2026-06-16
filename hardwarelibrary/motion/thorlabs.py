from hardwarelibrary.physicaldevice import *
from hardwarelibrary.motion.linearmotiondevice import *


class ThorlabsDevice(LinearMotionDevice):
    """Entry point for any Thorlabs motion stage.

    Constructing a ThorlabsDevice returns an instance of whichever backend is
    available on this machine, so callers do not have to know which transport
    is installed. The only backend at present is ThorlabsKinesisDevice, which
    drives the stage through the Thorlabs Kinesis runtime via pylablib.
    """

    @classmethod
    def backendClasses(cls):
        return [ThorlabsKinesisDevice]

    @classmethod
    def isAvailable(cls, serialNumber=None) -> bool:
        return False

    @classmethod
    def firstAvailableBackend(cls, serialNumber=None):
        for backend in cls.backendClasses():
            if backend.isAvailable(serialNumber):
                return backend
        raise PhysicalDevice.UnableToInitialize(
            "No Thorlabs backend available (pylablib/Kinesis not installed)")

    def __new__(cls, serialNumber=None):
        # Called as ThorlabsDevice(...): return a working backend instead of an
        # instance of this dispatcher. We make an *uninitialized* backend with
        # object.__new__ so Python runs __init__ exactly once, on the backend.
        if cls is not ThorlabsDevice:
            return super().__new__(cls)
        backend = cls.firstAvailableBackend(serialNumber)
        return super().__new__(backend)


class ThorlabsKinesisDevice(ThorlabsDevice):
    # Thorlabs' APT-over-FTDI identity; the transport itself is handled by the
    # Kinesis runtime through pylablib, not by us.
    classIdVendor = 0x0403
    classIdProduct = 0xfaf0

    @classmethod
    def isAvailable(cls, serialNumber=None) -> bool:
        try:
            import pylablib.devices.Thorlabs  # noqa: F401
            return True
        except Exception:
            return False

    def __init__(self, serialNumber: str = None):
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor, idProduct=self.classIdProduct)
        from pylablib.devices.Thorlabs import KinesisMotor
        self.dev = KinesisMotor(serialNumber, scale=(34554.96, 772981.3692, 263.8443072))

    def __del__(self):
        try:
            self.dev.close()
        except:
            # ignore if already closed
            return

    def doInitializeDevice(self):
        self.dev.home()

    def doShutdownDevice(self):
        self.dev.close()
        self.dev = None

    def positionInMicrosteps(self) -> (int, int, int):  # for compatibility
        return self.doGetPosition()

    def doGetPosition(self) -> (int, int, int):
        x = self.dev.get_position()
        return (x, None, None)

    def doMoveTo(self, position):
        x, y, z = position
        self.dev.move_to(x)

    def doMoveBy(self, displacement):
        dx, dy, dz = displacement
        self.dev.move_by(dx)

    def doHome(self):
        self.dev.home()
