import env
import unittest

import hardwarelibrary.communication.serialport as s_ports
from hardwarelibrary.motion.sutterdevice import SutterDevice


class TestConnectSutter(unittest.TestCase):
    def testConnectDebugSutter(self):
        sutter = SutterDevice(serialNumber="debug")
        # The port is not open until initializeDevice()
        sutter.doInitializeDevice()
        
        position = sutter.position()

        self.assertIsNotNone(position[0])
        self.assertIsNotNone(position[1])
        self.assertIsNotNone(position[2])

    def testMoveToWithDebugSutter(self):
        sutter = SutterDevice("debug")
        sutter.doInitializeDevice()

        sutter.moveTo((0, 100, 4000))
        position = sutter.position()
        self.assertTrue(position[0] == 0)
        self.assertTrue(position[1] == 100)
        self.assertTrue(position[2] == 4000)

    @unittest.skip("Must have real sutter connected")
    def testListStageDevices(self):
        sp = s_ports.SerialPort()
        ports = sp.matchPorts(idVendor=4930, idProduct=1)
        self.assertIsInstance(ports, list)
        self.assertTrue(ports)
        print(ports)
        # then we would try to match a port using the selected index. There is no function for that yet.
        sp.portPath = ports[0]
        sp.open(baudRate=128000)
        self.assertIsNotNone(sp.port)  # self.assertTrue(sp.isOpen())
        sp.close()

    @unittest.skip("Must have real sutter connected")
    def testConnectRealSutterWithSutterDeviceClass(self):
        sutter = SutterDevice()
        sp = s_ports.SerialPort()
        ports = sp.matchPorts(idVendor=4930, idProduct=1)
        portPath = ports[0]
        sutter.port = sp(portPath=portPath)  # we will have to generalize the method sutter.doInitializeDevice
        self.assertIsNotNone(sutter.port)
        sutter.port.open()
        self.assertIsNotNone(sp.port)
        sutter.moveTo((10, 4000, 100))
        position = sutter.position()
        self.assertTrue(position[0] == 10)
        self.assertTrue(position[1] == 4000)
        self.assertTrue(position[2] == 100)
        sutter.doShutdownDevice()

if __name__ == '__main__':
    unittest.main()

