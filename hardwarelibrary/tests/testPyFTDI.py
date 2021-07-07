import env # modifies path
import unittest
import pyftdi.serialext
import pyftdi.ftdi

class TestPyFTDIModule(unittest.TestCase):
    def testListPorts(self):
        a = pyftdi.ftdi.Ftdi.show_devices()
        self.assertIsNotNone(a)


if __name__ == '__main__':
    unittest.main()
