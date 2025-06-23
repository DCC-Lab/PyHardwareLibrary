import unittest


class BaseTestCases:
    device: CoboltDevice = None

    class TestCobolt(unittest.TestCase):

        def testCreate(self):
            self.assertIsNotNone(self.device)

        def testDeviceCreationWithMissingPath(self):
            aDevice = CoboltDevice(bsdPath="blabla")
            with self.assertRaises(PhysicalDeviceUnableToInitialize) as context:
                aDevice.initializeDevice()

        def testInitializeShutdown(self):
            self.device.initializeDevice()
            self.device.shutdownDevice()

        def testTurnOnWithAutostartOff(self):
            self.device.turnAutostartOff()
            self.device.turnOn()
            self.assertTrue(self.device.isLaserOn())
            self.device.turnAutostartOn()

        def testErrorTurnOnAutostartOn(self):
            self.device.turnAutostartOn()
            with self.assertRaises(CoboltCantTurnOnWithAutostartOn) as context:
                self.device.turnOn()

        def testTurnOffAutostartOn(self):
            self.device.turnAutostartOn()
            self.device.turnOff()
            self.assertFalse(self.device.isLaserOn())

        def testTurnOffAutostartOff(self):
            self.device.turnAutostartOff()
            self.device.turnOff()
            self.assertFalse(self.device.isLaserOn())

        def testTurnOnOff(self):
            self.device.turnAutostartOff()
            self.device.turnOn()
            self.assertTrue(self.device.isLaserOn())
            self.device.setPower(0.01)
            acceptableDifference = 0.1 * 0.01
            self.assertTrue(abs(self.device.power() - 0.01) < acceptableDifference)
            self.device.turnAutostartOn()

        def testGetAutostart(self):
            self.device.autostartIsOn()

        def testTurnAutostartOn(self):
            self.device.turnAutostartOn()
            self.assertTrue(self.device.autostartIsOn())

        def testTurnAutostartOff(self):
            self.device.turnAutostartOff()
            self.assertFalse(self.device.autostartIsOn())

        def testIsLaserOn(self):
            self.device.turnAutostartOff()
            self.device.turnOn()
            self.assertTrue(self.device.isLaserOn())
            self.device.turnAutostartOn()

        def testIsLaserOff(self):
            if not self.device.autostartIsOn:
                self.device.turnOn()
            self.assertFalse(self.device.isLaserOn())

        def testInterloc(self):
            self.assertTrue(self.device.interlock())

        def testAutostartOffOn(self):
            self.device.initializeDevice()
            self.device.turnAutostartOff()
            self.device.turnOn()
            self.device.turnAutostartOn()
            self.assertFalse(self.device.isLaserOn())


class TestDebugCobolt(BaseTestCases.TestCobolt):

    def setUp(self):
        self.device = CoboltDevice(bsdPath="debug")
        self.assertIsNotNone(self.device)
        self.device.initializeDevice()

    def tearDown(self):
        self.device.shutdownDevice()
        return


class TestRealCobolt(BaseTestCases.TestCobolt):

    def setUp(self):
        try:
            self.device = CoboltDevice(bsdPath="COM5")
            self.device.initializeDevice()
        except:
            raise unittest.SkipTest("No CoboltDevice at COM5")

    def tearDown(self):
        self.device.shutdownDevice()
        return


if __name__ == '__main__':
    unittest.main()
