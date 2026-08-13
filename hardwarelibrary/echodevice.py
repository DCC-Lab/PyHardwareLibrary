from hardwarelibrary.communication.debugport import ProtocolDebugPort
from hardwarelibrary.communication.protocol import CommandDictionary
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.physicaldevice import PhysicalDevice


# An echo sends its payload back verbatim, with nothing around it. There is no
# terminator to read up to, so a reply is a fixed-size frame -- and since the
# whole content is known in advance, every byte of it is a constant. That is what
# turns "we received something" into "we received exactly what we sent": a
# constant is required on the way in, so a reply that differs is refused.
echoProtocol = {
    "device": "FTDI echo device",
    "commands": {
        "ECHO1": {
            "request": {"struct": "<8s", "fields": ["text"],
                        "constants": {"text": "someText"}},
            "reply": {"struct": "<8s", "fields": ["text"],
                      "constants": {"text": "someText"}},
        },
        "ECHO2": {
            "request": {"struct": "<13s", "fields": ["text"],
                        "constants": {"text": "someOtherText"}},
            "reply": {"struct": "<13s", "fields": ["text"],
                      "constants": {"text": "someOtherText"}},
        },
        "ECHO3": {
            "request": {"struct": "<8s", "fields": ["data"],
                        "constants": {"data": "someData"}},
            "reply": {"struct": "<8s", "fields": ["data"],
                      "constants": {"data": "someData"}},
        },
    },
}


class EchoDevice(PhysicalDevice):
    """A device that sends back whatever it is given, over an FTDI cable.

    It exists to exercise the machinery rather than to measure anything, so its
    protocol is three payloads that must come back unchanged.
    """

    classIdProduct = 0x6001
    classIdVendor = 0x0403
    usesGenericSerialConverter = True

    protocol = CommandDictionary.fromDescription(echoProtocol)

    def __init__(self, serialNumber='ftDXIKC4', idProduct=classIdProduct,
                 idVendor=classIdVendor):
        """Bind to one FTDI cable, or to "debug" for a port that echoes in memory.

        Args:
            serialNumber: the cable's serial number, or "debug"
            idProduct: USB product id, defaulting to the class attribute
            idVendor: USB vendor id, defaulting to the class attribute
        """
        PhysicalDevice.__init__(self, serialNumber=serialNumber,
                                idProduct=idProduct, idVendor=idVendor)

    def doInitializeDevice(self):
        """Open the cable, or stand one up out of the description."""
        if self.serialNumber == "debug":
            self.port = ProtocolDebugPort(self.protocol)
        else:
            self.port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct)
        self.port.open()

    def doShutdownDevice(self):
        """Close the port."""
        self.port.close()
