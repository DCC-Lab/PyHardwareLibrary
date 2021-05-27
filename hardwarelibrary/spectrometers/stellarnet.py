from base import *
import stellarnet_driver3 as sn

class StellarNet(Spectrometer):
    idVendor = 0x04b4  # StellarNet does not have a USB vendor.
    idProduct = 0x8613 # they use the Cypress USB Dev kit
    timeScale = 1 # milliseconds=1, microseconds=1000

    def __init__(self):
        self.model = "BlackComet StellarNet"
        self.stellarNetHandle = None
        try:
            self.stellarNetHandle, wav = sn.array_get_spec(0)
        except:
            raise NoSpectrometerConnected("Unable to find a Stellarnet Spectrometer")

        self.wavelength = np.array(wav)
        self.integrationTime = 10

    def getSerialNumber(self):
        return "No serial number provided"

    def getSpectrum(self):
        device = self.stellarNetHandle['device']
        device.set_config(int_time=int(self.integrationTime), scans_to_avg=1, x_smooth=1)
        zippedSpectrum = sn.array_spectrum(self.stellarNetHandle, self.wavelength)
        _, spectrum = list(zip(*zippedSpectrum))
        return spectrum


if __name__ == "__main__":
    try:
        if len(sys.argv) == 1:
            spectrometer = StellarNet()
            spectrometer.getSpectrum()
        else: # any argument will do. Shh!
            spectrometer = DebugSpectro()

        spectrometer.display()

    except usb.core.NoBackendError as err:
        Spectrometer.showHelp("PyUSB does not find any 'backend' to communicate with the USB ports (e.g., libusb is not found anywhere).")
    except NoSpectrometerConnected as err:
        Spectrometer.showHelp("No spectrometers detected: you can use `python oceaninsight.py debug` for testing")
    except Exception as err:
        """ Something unexpected occurred, which is probably a module not available.
        We show some help and the error.
        """
        Spectrometer.showHelp(err)
