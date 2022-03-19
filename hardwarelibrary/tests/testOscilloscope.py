import env
import os
import unittest
import time
import struct

from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from hardwarelibrary.oscilloscope import *

class TestTektronik(unittest.TestCase):

    def testCreate(self):
        self.device = OscilloscopeDevice()
        self.assertIsNotNone(self.device)

    def testInit(self):
        self.device = OscilloscopeDevice()
        self.device.initializeDevice()
        self.device.shutdownDevice()

    def testGetWaveform(self):
        self.device = OscilloscopeDevice()
        self.device.initializeDevice()
        self.device.getWaveform(Channels.CH1)
        self.device.getWaveform(Channels.CH2)
        self.device.shutdownDevice()

    def testDisplayWaveform(self):
        self.device = OscilloscopeDevice()
        self.device.initializeDevice()
        self.device.displayWaveforms([Channels.CH1, Channels.CH2])
        self.device.shutdownDevice()

    def testDisplayWaveform(self):
        self.device = OscilloscopeDevice()
        self.device.initializeDevice()
        self.device.displayWaveforms([Channels.CH1, Channels.CH2])
        self.device.shutdownDevice()


@unittest.skip("For understanding earlier on, not necessary anymore")
class TestTektronikSerialCommands(unittest.TestCase):
    idVendor = 0x0403
    idProduct = 0x6001

    port = None
    def setUp(self):
        self.port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct)
        self.assertIsNotNone(self.port)
        self.port.open(baudRate=9600, timeout=5.0, rtscts=True)
        self.assertTrue(self.port.isOpen)
        self.port.flush()
        self.getStatus()


    def tearDown(self):
        if self.port is not None:
            self.port.close()
            self.port = None

    @unittest.skip("Now in setup")
    def test01CanFindPort(self):
        port = SerialPort(idVendor=self.idVendor, idProduct=self.idProduct)
        self.assertIsNotNone(port)

    @unittest.skip("Now in setup")
    def test02CanOpenPort(self):
        self.port.open(baudRate=19200)
        self.assertTrue(self.port.isOpen)

    def test03ScopeIdentification(self):
        groups = self.port.writeStringReadMatchingGroups(string="ID?\n", replyPattern="ID (TEK.*?),.+")
        self.assertTrue(len(groups) == 2)


    def test04ScopeWaveform(self):
        channel = Channels.CH1
        command = "DATA:SOURCE {0}\n".format(channel.value)
        self.writeString(string=command)
        time.sleep(0.5)

        try:
            self.writeString(string="CURVE?\n")
            nValues = self.readBlockSize()
            data = self.readData(nValues) 
            self.readData(1) # drop newline
            self.assertEqual(len(data), nValues)
            values = struct.unpack("{0}b".format(nValues), data)
            self.assertEqual(len(values), nValues)
        except Exception as err:
            print(self.getStatus())
            print(err)
        
        hasError,_,_,_ = self.getStatus()
        self.assertFalse(hasError)

        self.writeString(string="WFMPRE:XINCR?\n")
        xIncr = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.writeString(string="WFMPRE:PT_OFF?\n")
        ptOffset = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.writeString(string="WFMPRE:XZERO?\n")
        xZero = float(self.readFirstMatchingGroup(r"(\d.*)$"))

        self.writeString(string="WFMPRE:YMUL?\n")
        yMul = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.writeString(string="WFMPRE:YOFF?\n")
        yOffset = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.writeString(string="WFMPRE:YZERO?\n")
        yZero = float(self.readFirstMatchingGroup(r"(\d.*)$"))


        calibratedValues = [(xZero + xIncr*(i-ptOffset), yZero + (value-yOffset)*yMul ) for i,value in enumerate(values) ]
        [ print(x,y) for x,y in calibratedValues ]

    # def test041ScopeWaveformSourceSelection(self):
    #     for expected in Channels:
    #         command = "DATA:SOURCE {0}\n".format(expected.value)
    #         self.writeString(string=command)
    #         command = "DATA:SOURCE?\n"
    #         self.writeString(string=command)
    #         current = Channels(self.readFirstMatchingGroup("(.*?)$"))
    #         self.assertEqual(current, expected)


    # @unittest.skip("Long")
    # def test05ManyScopeWaveforms(self):
    #     for i in range(2):
    #         self.writeString(string="CURVE?\n")
    #         nValues = self.readBlockSize()
    #         data = self.port.readData(nValues)
    #         self.port.readData(1) # drop newline    
    #         self.assertEqual(len(data), nValues)
    #         values = struct.unpack("{0}b".format(nValues), data)

    def readBlockSize(self):
        blockDelimiter = self.readData(length=1)
        if blockDelimiter != b'#':
            raise ValueError("Bad block delimiter {0}".format(blockDelimiter))
        nDigits = int(self.readData(length=1).decode('utf-8'))
        nValues = int(self.readData(length=nDigits).decode('utf-8'))
        return nValues

    # def test06ManyCommandsAndReplies(self):
        # print(self.port.writeStringExpectMatchingString(string="DATA:SOURCE?\n", replyPattern="(.*)"))
        # print(self.port.writeStringReadMatchingGroups(string="DATA?\n", replyPattern="(.*);(.*);(.*);(.*);(.*);(.*).+"))
        # print(self.port.writeStringReadMatchingGroups(string="DATA:DEST?\n", replyPattern="(.*)"))
    # def test10StatusByte(self):
    #     self.writeString(string="*STB?\n")
    #     stb = self.readString()
    #     self.writeString(string="*ESR?\n")
    #     esrByte = self.readString()

    # def test11Busy(self):
    #     self.writeString(string="BUSY?\n")
    #     reply = self.readString()

    def writeString(self, string):
        time.sleep(0.1)
        self.assertTrue(self.port.port.cts)
        return self.port.writeString(string=string)

    def readString(self):
        time.sleep(0.1)
        self.assertTrue(self.port.port.dsr)
        return self.port.readString()

    def readFirstMatchingGroup(self, replyPattern, alternatePattern = None, endPoint=None):
        reply, groups = self.readMatchingGroups(replyPattern, alternatePattern, endPoint)
        return groups[0]

    def readMatchingGroups(self, replyPattern, alternatePattern = None, endPoint=None):
        time.sleep(0.1)
        return self.port.readMatchingGroups(replyPattern, alternatePattern, endPoint)

    def readData(self, length):
        time.sleep(0.1)
        return self.port.readData(length)

    def getStatus(self):

        stb = None
        esrByte = None
        errors = {}

        while True:
            try:
                self.writeString(string="*STB?\n")
                stb = self.readString()
                self.writeString(string="*ESR?\n")
                esrByte = self.readString()

                self.writeString(string="EVQTY?\n")
                evQty = int(self.readString())

                if evQty != 0:
                    baseReg = r"(\d+),\"(.*?)\""
                    regexp = ",".join([baseReg]*evQty)
                    self.writeString(string="ALLEV?\n")
                    reply, groups = self.readMatchingGroups(replyPattern=regexp)
                    errors = { int(groups[i]):TektronikException(code=int(groups[i]), msg=groups[i + 1], esr=esrByte, stb=stb) for i in range(0, len(groups), 2) }
                break
            except Exception as err:
                self.port.flush()
                print(err)
                time.sleep(4.0)
                pass

        if stb is not None:
            stb = int(stb)
        if esrByte is not None:
            esrByte = int(esrByte)

        return len(errors) != 0, stb, esrByte, errors

    # def testStatus(self):
    #     for _ in range(10):
    #         hasError, stb, esrByte, errors = self.getStatus()
    #         self.assertIsNotNone(stb)
    #         self.assertIsNotNone(esrByte)
    #         self.assertIsNotNone(errors)

    def test09BadCommand(self):
        self.writeString(string="DATA\n") # incomplete command

        hasError, stb, esrByte, errors = self.getStatus()
        self.assertTrue(100 in errors)
        self.assertTrue(hasError)

    def test09ManyCommandsAndReplies(self):
        self.writeString(string="INVALID\n") # invalid command
        hasError, stb, esrByte, errors = self.getStatus()
        self.assertTrue(113 in errors)
        self.assertTrue(hasError)

    # def testCompoundCOmmands(self):
    #     print(self.port.writeStringReadMatchingGroups(string="DATA?\n", replyPattern="(.*);(.*);(.*);(.*);(.*);(.*)"))
    #     hasError, stb, esrByte, errors = self.getStatus()
    #     self.assertTrue(esr == 0)

    #     print(self.writeString(string="DATA:ENCDG?\n"))
    #     try:
    #         print(self.readMatchingGroups("(.*)"))
    #     except Exception as err:
    #         hasError, stb, esrByte, errors = self.getStatus()
    #         print(errors)
    #     # self.port.writeString(string="DATA:SOURCE?\n")
    #     # # time.sleep(1)
    #     # print(self.port.readString())

    def test06Timescale(self):
        self.writeString(string="HORizontal:MAIN:SCALE?\n")
        print(self.readString()) #The scale on time button

    def test16VoltageScale(self):
        self.writeString(string="CH1:VOLTS?\n")
        print(self.readString()) # the scale in volts per div

    def hasError(self):
        hasError,_,_,_ = self.getStatus()
        return hasError

    def test17WfmPreamble(self):
        self.writeString(string="WFMPRE:XINCR?\n")
        xIncr = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.assertFalse(self.hasError())
        self.writeString(string="WFMPRE:PT_OFF?\n")
        ptOffset = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.assertFalse(self.hasError())
        self.writeString(string="WFMPRE:XZERO?\n")
        xZero = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.assertFalse(self.hasError())

        self.writeString(string="WFMPRE:YMUL?\n")
        yMul = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.assertFalse(self.hasError())
        self.writeString(string="WFMPRE:YOFF?\n")
        yOffset = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.assertFalse(self.hasError())
        self.writeString(string="WFMPRE:YZERO?\n")
        yZero = float(self.readFirstMatchingGroup(r"(\d.*)$"))
        self.assertFalse(self.hasError())

if __name__ == '__main__':
    unittest.main()


