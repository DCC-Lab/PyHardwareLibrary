import unittest
import os
import time

class APTTest(unittest.TestCase): 

	add_libftd2xx_and_path_instructions = """
		FIRST : You must download and install the libftd2xx.dylib library

		https://ftdichip.com/drivers/d2xx-drivers/

		From the Readme.rtf:

		Installing the library is a relatively simple operation which involves
		copying a file and making a symbolic link. Use the following steps
		to install (these assume you have copied the distribution’s D2XX
		folder to the desktop):

		1. Open a Terminal window (Finder->Go->Utilities->Terminal). 

		2. If the /usr/local/lib directory does not exist, create it: sudo
		mkdir /usr/local/lib 

		3. if the /usr/local/include directory does
		not exist, create it: sudo mkdir /usr/local/include 

		4. Copy the dylib file to /usr/local/lib: sudo cp
		Desktop/release/build/libftd2xx.1.4.30.dylib /usr/local/lib/libftd2xx.1.4.30.dylib
		
		5. Make a symbolic link: sudo
		ln -sf /usr/local/lib/libftd2xx.1.4.30.dylib /usr/local/lib/libftd2xx.dylib
		
		6. Copy the D2XX include file: sudo cp
		Desktop/release/ftd2xx.h /usr/local/include/ftd2xx.h 

		7. Copy the WinTypes include file: sudo cp
		Desktop/release/WinTypes.h /usr/local/include/WinTypes.h 8. You
		have now successfully installed the D2XX library.


		SECOND: Must do this on command-line or in .zshrc:

		export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH

		then call python from same shell or include it in your .zprofile or .zshrc.

		You cannot try to do it form Python because it is not possible to
		change the DYLD_PATH for signed binaries on macOS

		dyldpath = os.environ.get("DYLD_LIBRARY_PATH", "") os.environ
		['DYLD_LIBRARY_PATH'] = f"/usr/local/lib:{dyldpath}"

		THIRD: You must add Thorlabs' VIDPID  before using pylablib:

		import ctypes as c lib = c.CDLL("libftd2xx.dylib") lib.FT_SetVIDPID
		(0x0403, 0xFAF0)

		"""

	@classmethod
	def add_thorlabs_vidpid(cls):
		"""
		We add the VIDs/PIDs of Thorlabs to be recognized.

		Only FTDI VID and its own generic PIDs are in the list by default

		Important: the dynamic library that is loaded is a single instance.
		Therefore, if we load it here and modify it, then the modification will be global.

		"""
		import ctypes as c
		lib = c.CDLL("libftd2xx.dylib")
		lib.FT_SetVIDPID(0x0403, 0xFAF0)

	@classmethod
	def setUpClass(cls):
		try:
			cls.add_thorlabs_vidpid()
		except Exception as err:
			print(f"Error when adding vid_pid: {err}\n\n")

			print(cls.add_libftd2xx_and_path_instructions)

	def test_001_start_here_the_problem(self):
		"""
		On a pristine Python3.13 and a APT device connected with pylablib,
		this will faill with an error: 

		1. either the python code will raise an exception with libraries 

		2. or it will return an empty list of device

		When the present test passes, the problem is solved.

		"""
		from pylablib.devices.Thorlabs import kinesis

		devices = kinesis.KinesisDevice.list_devices()
		if devices is not None:
			self.assertTrue(len(devices) > 0 )

	def test_002_usrlocal_in_dyld_path(self):
		"""
		The libftd2xx.dylib is necessarily in a usr-controlled lib, not
		system /usr/lib/ since they are not modifiable If
		DYLD_LIBRARY_PATH is empty, then for sure this will fail. 
		"""
		dyldpath = os.environ.get("DYLD_LIBRARY_PATH", "")

		self.assertTrue(len(dyldpath) > 0, self.add_libftd2xx_and_path_instructions)
		self.assertTrue("/usr/local/lib" in dyldpath or "/opt/homebrew/lib" in dyldpath, self.add_libftd2xx_and_path_instructions)

	def test_003_able_to_import_library(self):
		import ctypes as c

		try:
			lib = c.cdll.LoadLibrary("libftd2xx.dylib")
		except:
			self.fail(f"The library libftd2xx.dylib is not found in the DYLD_LIBRRY_PATH='{os.environ.get('DYLD_LIBRARY_PATH', '')}'")

	def test_004_are_thorlabs_vidpid_recognized(self):
		"""
		The thorlabs VID and PID are not included by default in the libftd2xx list
		of VIDs/PIDs to recognize.  However, the list can be modified (and must be modified)

		"""
		from pylablib.devices.Thorlabs import kinesis

		devices = kinesis.KinesisDevice.list_devices()
		if devices is not None:
			self.assertTrue(len(devices) > 0 )

		for i, device in enumerate(devices):
			print(f"Device available: {device}")

	def test_005_kinesis_access_works(self):
		"""
		If all the fixes above were properly done, this code will work

		"""
		from pylablib.devices.Thorlabs import kinesis, KinesisMotor

		devices = kinesis.KinesisDevice.list_devices()
		if len(devices) == 1:
			serial_number, name = devices[0]

		dev = KinesisMotor(serial_number, scale=(34554.96, 772981.3692, 263.8443072))

		dev.home()

		# calibration = {"Z812B":{"pitch":0.001, "steps_per_rev":34_554}}

		cal_pos, cal_speed, cal_acc = dev.get_scale()
		print(dev.setup_velocity(acceleration=700, max_velocity=3))

		print(f"Scale units: {dev.get_scale_units()}")
		print(f"Scale value: {cal_pos, cal_speed, cal_acc}")
		print(f"Velocity parameters: {dev.get_velocity_parameters()}")


		self.move_to_synchronously(dev, 0)
		self.move_to_synchronously(dev, 10)
		self.move_to_synchronously(dev, 5)
		dev.close()

	@staticmethod
	def move_to_synchronously(dev, target):
		print(f"Moving to {target}")
		dev.move_to(target)
		start_time = time.time()
		prev_status = None
		while time.time() - start_time < 10:
			time.sleep(0.2)
			status = dev.get_status()[0]
			if status != prev_status:
				print(f"Status {status}")
			prev_status = status
			if status == 'connected' and abs(dev.get_position() - target) < 0.01:
				break
		print(f"Done {dev.get_position()}")

if __name__ == "__main__":
	unittest.main()
