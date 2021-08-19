import unittest
from hardwarelibrary.motion.sutterdevice import SutterDevice


class TestMapPositionsFunction(unittest.TestCase):
    def setUp(self):
        # pyftdi.ftdi.Ftdi.add_custom_product(vid=4930, pid=1, pidname='Sutter')
        try:
            self.device = SutterDevice()
            self.device.initializeDevice()
        except:
            self.device = SutterDevice("debug")
            self.device.initializeDevice()
            # print("Using Debug Sutter device for tests")

        self.assertIsNotNone(self.device)
        # raise(unittest.SkipTest("No FTDI connected. Skipping."))

    def tearDown(self):
        self.device.shutdownDevice()
        self.device = None

    def testInverseRangeDoesntSeemToWork(self):
        testList = []
        for i in range(5, 0, -1):
            testList.append(i)
        for ind, el in enumerate(testList):
            self.assertEqual(ind, 5-el)

    def testListIsCompleteInZigzagMap(self):
        map = self.device.mapPositions(2, 2, 1, "zigzag")
        print(map)
        self.assertIsInstance(map, list)
        for i in range(4):
            self.assertIsInstance(map[i], tuple)
            self.assertTrue(len(map[i]) == 3)
        self.assertTrue(len(map) == 4)

    def testListIsCompleteInLeftRightMap(self):
        map = self.device.mapPositions(2, 2, 3, "leftRight")
        self.assertIsInstance(map, list)
        for i in range(4):
            self.assertIsInstance(map[i], tuple)
            self.assertTrue(len(map[i]) == 3)
        self.assertTrue(len(map) == 4)

    def testMoveToFromPositionsGivenWithLeftRight(self):
        map = self.device.mapPositions(2, 2, 3, "leftRight")
        for pos in map:
            self.device.moveTo(pos)
            self.assertEqual(pos, self.device.position())

    def testMoveToFromPositionsGivenWithZigzag(self):
        map = self.device.mapPositions(2, 2, 3, "zigzag")
        for pos in map:
            self.device.moveTo(pos)
            self.assertEqual(pos, self.device.position())

    def testListWithInitialPositionNotWorkingForNow(self):
        self.device.moveTo((5, 5, 5))
        map = self.device.mapPositions(2, 2, 3, "leftRight")
        print(map)
        for pos in map:
            self.device.moveTo(pos)
            self.assertEqual(pos, self.device.position())
