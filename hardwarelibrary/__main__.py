import os 
import sys
import argparse
import re
import subprocess
from pathlib import Path
import platform
import hardwarelibrary.spectrometers as spectro
from hardwarelibrary import DeviceManager

import signal
import sys

def signal_handler(sig, frame):
    dm = DeviceManager()
    if dm.isMonitoring and not dm.quitMonitoring:
        print('Quitting nicely')
        dm.stopMonitoring()

signal.signal(signal.SIGINT, signal_handler)

 # We start by figuring out what the user really wants. If they don't know,
# we offer some help
ap = argparse.ArgumentParser(prog='python -m hardwarelibrary')
ap.add_argument("-stellar", "--stellarnet", required=False, action='store_const',
                const=True, help="Decrypt the StellarnNet driver.  Contact StellarNet for info.")
ap.add_argument("-s", "--spectrometer", required=False, action='store_const',
                const=True, help="Display any spectrometer")
ap.add_argument("-dm", "--devicemanager", required=False, action='store_const',
                const=True, help="Show notifications from DeviceManager")
ap.add_argument("-d", "--debugusb", required=False, action='store_const',
                const=True, help="Help debugging USB libraries issues")

args = vars(ap.parse_args())
decrypt = args['stellarnet']
displaySpectrum = args['spectrometer']
deviceManager = args['devicemanager']
debugUSB = args['debugusb']

if decrypt == True:
    rootHardwareLibrary = Path(os.path.abspath(__file__)).parents[1]
    spectrometersDirectory = rootHardwareLibrary.joinpath('hardwarelibrary/spectrometers')
    zipFile =spectrometersDirectory.joinpath('stellarnet.zip')

    if platform.system() == 'Windows':
        os.startfile(zipFile)
    elif platform.system() == 'Darwin':
        completedProcess = subprocess.run(["unzip", zipFile, "-d", spectrometersDirectory])
        if completedProcess.returncode != 0:
            print("There was an error when unzipping and decrypting the stellarnet.zip file")
    else:
        print('Cannot unzip stellarnet file, you must unzip it manually : {0}'.format(zipFile))

if displaySpectrum == True:
    spectro.displayAny()

if deviceManager == True:
    dm = DeviceManager()
    dm.showNotifications()
    dm.startMonitoring()

if debugUSB == True:
    from hardwarelibrary.communication import validateUSBBackend
    backend = validateUSBBackend(verbose=True)
    if backend is not None:
        print("PyUSB found and uses backend from: {0}".format(backend.lib))
    else:
        print("PyUSB has not found a backend to operate.")