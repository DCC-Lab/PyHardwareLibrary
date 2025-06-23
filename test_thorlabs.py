import unittest
import serial
from serial.tools.list_ports import *
from hardwarelibrary.communication import USBPort


class ThorlabsTestCase(unittest.TestCase):
	def test00_init(self):
		self.assertTrue(True)

	def test01_import_serial_port(self):
		import serial # si pas intalle, exception

	def test02_find_port(self):
		for port in grep("cu"):
			print(port)

	@unittest.expectedFailure
	def test03_pyftdi(self):
		import pyftdi.serialext
		from pyftdi.ftdi import Ftdi
		self.assertIsNotNone(Ftdi.show_devices())

	def test04_pyhardwarelibrary(self):
		print(USBPort.allDevices())

	def test05_open_thorlabs_port(self):
		port = USBPort(idVendor=0x0403, idProduct=0xfaf0, defaultEndPoints=(1,0))
		self.assertIsNotNone(port)
		port.open()


if __name__ == "__main__":
	unittest.main()

