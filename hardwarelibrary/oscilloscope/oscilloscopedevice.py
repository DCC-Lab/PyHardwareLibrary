import time
from enum import Enum
import struct
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
import matplotlib.pyplot as plt

class Channels(Enum):
    CH1     = "CH1"
    CH2     = "CH2"
    MATH    = "MATH"
    REFA    = "REFA"
    REFB    = "REFB"

class TektronikException(Exception):
    def __init__(self, code, msg, esr, stb, underlyingErrors=None):
        self.code = code
        self.msg = msg
        self.esr = esr
        self.stb = stb
        self.underlyingErrors = underlyingErrors
        
        super().__init__(msg)

class OscilloscopeDevice(PhysicalDevice):
    classIdVendor = 0x0403
    classIdProduct = 0x6001

    def __init__(self, serialNumber:str = None, idProduct = 0x6001, idVendor = 0x0403):
        super().__init__(serialNumber, idProduct=self.classIdProduct, idVendor=self.classIdVendor)

        self.port = SerialPort(idVendor=self.classIdVendor, idProduct=self.classIdProduct)
        self.delay = None

    def displayWaveforms(self, channels=None):
        if channels is None:
            channels = [Channels.CH1, Channels.CH2]

        plt.style.use('https://raw.githubusercontent.com/dccote/Enseignement/master/SRC/dccote-errorbars.mplstyle')

        for channel in channels:
            waveform = self.getWaveform(channel)
            x,y = zip(*waveform)
            if channel == Channels.CH1:
                marker = 'k-'
            else:
                marker = 'k--'
            plt.plot(x,y,marker)
        
        plt.ylabel("Voltage [V]")
        plt.xlabel("Time [s]")
        plt.show()

    def getWaveform(self, channel):
        self.doSendCommand("SELECT:{0} ON\n".format(channel.value))
        self.doSendCommand("DATA:SOURCE {0}\n".format(channel.value))

        xIncr = self.doSendFloatQuery("WFMPRE:XINCR?\n")
        ptOffset = self.doSendFloatQuery("WFMPRE:PT_OFF?\n")
        xZero = self.doSendFloatQuery("WFMPRE:XZERO?\n")
        yMul = self.doSendFloatQuery("WFMPRE:YMUL?\n")
        yOffset = self.doSendFloatQuery("WFMPRE:YOFF?\n")
        yZero = self.doSendFloatQuery("WFMPRE:YZERO?\n")

        self.port.writeString("CURVE?\n")
        values = self.doReadBinaryBlock()

        return [(xZero + xIncr*(i-ptOffset), yZero + (value-yOffset)*yMul ) for i,value in enumerate(values) ]

    def doInitializeDevice(self):
        if self.port is not None:
            self.port.open(baudRate=9600, timeout=5.0, rtscts=True)
            self.doGetTektronikStatus()
            # self.model = self.doSendQuery("ID?\n", "ID (TEK.*?),.+")

    def doShutdownDevice(self):
        if self.port is not None:
            self.port.close()

    def wait(self):
        if self.delay is not None:
            time.sleep(self.delay)

    def doSendQuery(self, query, replyPattern):
        try:
            self.wait()
            self.port.writeString(string=query)
            self.wait()
            return self.port.readMatchingGroups(replyPattern)
        except Exception as err:
            tekError = self.doGetTektronikError()
            if tekError is not None:
                raise tekError
            else:
                raise err

    def doSendFloatQuery(self, query):
        reply, groups = self.doSendQuery(query, r"(\d.*)$")
        return float(groups[0])

    def doSendIntQuery(self, query):
        reply, groups = self.doSendQuery(query, r"(\d.*)$")
        return int(groups[0])

    def doSendCommand(self, command):
        self.wait()
        self.port.writeString(string=command)
        tekError = self.doGetTektronikError()
        if tekError is not None:
            raise tekError

    def doReadBinaryBlock(self):
        self.wait()
        try:
            blockDelimiter = self.port.readData(length=1)
            if blockDelimiter != b'#':
                raise ValueError("Bad block delimiter {0}".format(blockDelimiter))
            nDigits = int(self.port.readData(length=1).decode('utf-8'))
            nValues = int(self.port.readData(length=nDigits).decode('utf-8'))

            data = self.port.readData(nValues) 
            self.port.readData(1) # drop newline
            values = struct.unpack("{0}b".format(nValues), data)
        except Exception as err:
            tekError = self.doGetTektronikError()
            if tekError is not None:
                tekError.underlyingErrors = [err]
                raise tekError
            else:
                raise err

        return values

    def doGetTektronikStatus(self):

        stb = None
        esr = None
        errors = []

        while True:
            try:
                stb = self.doSendIntQuery("*STB?\n")
                esr = self.doSendIntQuery("*ESR?\n")
                evQty = self.doSendIntQuery("EVQTY?\n")

                if evQty != 0:
                    baseReg = r"(\d+),\"(.*?)\""
                    regexp = ",".join([baseReg]*evQty)
                    self.port.writeString(string="ALLEV?\n")
                    reply, groups = self.port.readMatchingGroups(replyPattern=regexp)
                    errors = [TektronikException(code=int(groups[i]), msg=groups[i + 1], esr=esr, stb=stb) for i in range(0, len(groups), 2) ]
                break
            except Exception as err:
                self.port.flush()
                return True, 0,0, [RuntimeError("Unable to read oscilloscope status")]

        if stb is not None:
            stb = int(stb)
        if esr is not None:
            esr = int(esr)

        return len(errors) != 0, stb, esr, errors


    def doGetStatusUserInfo(self):
        return self.doGetTektronikStatus()

    def doGetTektronikError(self):
        hasError, _, _ , errors = self.doGetTektronikStatus()
        if hasError:
            return errors[0]
        return None

    @classmethod
    def showHelp(cls, err=None):
        print("This OscilloscopeDevice works with Tektronik scopes only (and was tested with a TDS-1002)")

        print("""    There was an error when starting: '{0}'.
    See above for help.""".format(err))


if __name__ == "__main__":
    scope = OscilloscopeDevice()
    scope.displayWaveforms()
