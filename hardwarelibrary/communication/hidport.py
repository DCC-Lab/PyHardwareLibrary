from .communicationport import CommunicationPort, CommunicationReadTimeout


class HIDPort(CommunicationPort):
    """A CommunicationPort over a USB HID device, backed by hidapi.

    HID is the only way to reach a device the operating system claims as HID.
    On macOS the IOHIDFamily driver owns the interface, so neither SerialPort
    (there is no /dev node) nor USBPort (libusb cannot claim the interface) can
    open it; hidapi goes through the same IOKit HID manager the OS reserves.

    This exposes the same primitives as SerialPort/USBPort (open/close/
    readData/writeData/flush), so a driver written against CommunicationPort
    works unchanged. It requires the optional 'hidapi' dependency (imported as
    'hid'); the import is deferred to open() so the rest of the library does not
    depend on it.

    hidapi frames every report with the report ID as byte 0. Devices that use a
    single unnumbered report expect that byte to be 0x00; writeData prepends it,
    and the count it returns excludes it.
    """

    def __init__(self, idVendor, idProduct, serialNumber=None):
        super().__init__()
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.serialNumber = serialNumber
        self.device = None
        self.defaultTimeout = 500
        self.reportSize = 64
        # Bounded drain for flush(): a small positive per-read timeout (never 0,
        # which blocks in hidapi rather than returning immediately) and a cap on
        # the number of reports drained, so flush can never hang.
        self.drainTimeout = 2
        self.maxDrainReports = 16
        self._internalBuffer = bytearray()

    @property
    def isOpen(self) -> bool:
        return self.device is not None

    def open(self):
        if self.isOpen:
            raise Exception("Port already open")

        import hid
        self.device = hid.device()
        if self.serialNumber in (None, "*", ".*"):
            self.device.open(self.idVendor, self.idProduct)
        else:
            self.device.open(self.idVendor, self.idProduct, self.serialNumber)
        self._internalBuffer = bytearray()

    def close(self):
        with self.portLock:
            if self.device is not None:
                self.device.close()
                self.device = None
            self._internalBuffer = bytearray()

    def bytesAvailable(self, endPoint=None) -> int:
        with self.portLock:
            return len(self._internalBuffer)

    def flush(self, endPoint=None):
        with self.portLock:
            self._internalBuffer = bytearray()
            if self.device is None:
                return
            # timeout_ms must stay positive: hidapi blocks on 0. The cap bounds
            # the wait even if a device were to stream input reports.
            for _ in range(self.maxDrainReports):
                if not self.device.read(self.reportSize, timeout_ms=self.drainTimeout):
                    break

    def readData(self, length, endPoint=None) -> bytearray:
        with self.portLock:
            while length > len(self._internalBuffer):
                chunk = self.device.read(self.reportSize, timeout_ms=self.defaultTimeout)
                if not chunk:
                    raise CommunicationReadTimeout(
                        "Read {0} of {1} requested bytes from HID device".format(
                            len(self._internalBuffer), length))
                self._internalBuffer += bytearray(chunk)

            data = self._internalBuffer[:length]
            self._internalBuffer = self._internalBuffer[length:]

        return data

    def writeData(self, data, endPoint=None) -> int:
        with self.portLock:
            # Byte 0 is the HID report ID (0x00 for a single, unnumbered report).
            written = self.device.write(bytes([0x00]) + bytes(data))
            if written < 0:
                raise IOError("Unable to write to HID device")

        return max(0, written - 1)
