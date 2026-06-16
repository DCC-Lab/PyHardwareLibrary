import env
import os
import time
import unittest

# Bringing the Thorlabs Kinesis/APT stack up on macOS is fiddly. These notes are
# kept with the tests because the checks below only run once the stack is set up;
# when it is not, every test skips and prints these instructions as the reason.
SETUP_INSTRUCTIONS = """
    FIRST: Download and install the libftd2xx.dylib library
    https://ftdichip.com/drivers/d2xx-drivers/

    Copy the dylib into a user-writable lib directory and symlink it, e.g.:
        sudo cp libftd2xx.1.4.30.dylib /usr/local/lib/
        sudo ln -sf /usr/local/lib/libftd2xx.1.4.30.dylib /usr/local/lib/libftd2xx.dylib

    SECOND: Expose it on the loader path (in the shell that launches Python; you
    cannot set DYLD_LIBRARY_PATH from inside a signed Python on macOS):
        export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH

    THIRD: Thorlabs' VID/PID is not recognized by libftd2xx by default; it must
    be registered before pylablib can enumerate the stage:
        import ctypes
        lib = ctypes.CDLL("libftd2xx.dylib")
        lib.FT_SetVIDPID(0x0403, 0xFAF0)
"""


def kinesisEnvironmentError():
    """Return why the Kinesis/FTDI stack is unusable on this host, or None if it
    looks ready.

    Lets the hardware tests skipTest() cleanly when libftd2xx, its loader-path
    entry, the pylablib FTDI backend, or a connected stage is missing, rather
    than failing the suite on a machine without a Thorlabs device attached.
    """
    import ctypes

    try:
        lib = ctypes.cdll.LoadLibrary("libftd2xx.dylib")
        # Thorlabs IDs are not in libftd2xx's default list; register them so the
        # stage enumerates. The library is a single shared instance, so this
        # registration is global once applied.
        lib.FT_SetVIDPID(0x0403, 0xFAF0)
    except OSError:
        dyldPath = os.environ.get("DYLD_LIBRARY_PATH", "")
        return f"libftd2xx.dylib not loadable (DYLD_LIBRARY_PATH={dyldPath!r})"

    try:
        from pylablib.devices.Thorlabs import kinesis
        devices = kinesis.KinesisDevice.list_devices()
    except Exception as error:
        # e.g. pylablib's FTDI backend (FT232DeviceBackend) is unavailable on
        # this pylablib build, or the d2xx package is missing.
        return f"pylablib Kinesis backend unavailable: {error}"

    if not devices:
        return "No Thorlabs Kinesis/APT device connected"
    return None


class APTTest(unittest.TestCase):
    def setUp(self):
        reason = kinesisEnvironmentError()
        if reason is not None:
            self.skipTest(f"{reason}\n{SETUP_INSTRUCTIONS}")

        from pylablib.devices.Thorlabs import kinesis
        self.devices = kinesis.KinesisDevice.list_devices()

    def testDevicesAreListed(self):
        self.assertTrue(len(self.devices) > 0)
        for device in self.devices:
            print(f"Device available: {device}")

    def testKinesisMotorAccessAndMove(self):
        from pylablib.devices.Thorlabs import KinesisMotor

        serialNumber, name = self.devices[0]
        motor = KinesisMotor(serialNumber, scale=(34554.96, 772981.3692, 263.8443072))
        try:
            motor.home()
            self.moveToSynchronously(motor, 0)
            self.moveToSynchronously(motor, 10)
            self.moveToSynchronously(motor, 5)
        finally:
            motor.close()

    @staticmethod
    def moveToSynchronously(motor, target):
        print(f"Moving to {target}")
        motor.move_to(target)
        startTime = time.time()
        previousStatus = None
        while time.time() - startTime < 10:
            time.sleep(0.2)
            status = motor.get_status()[0]
            if status != previousStatus:
                print(f"Status {status}")
            previousStatus = status
            if status == "connected" and abs(motor.get_position() - target) < 0.01:
                break
        print(f"Done {motor.get_position()}")


if __name__ == "__main__":
    unittest.main()
