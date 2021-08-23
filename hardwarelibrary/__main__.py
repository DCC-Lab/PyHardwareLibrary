import os 
import sys
import argparse
import re
import subprocess
from pathlib import Path
import platform

 # We start by figuring out what the user really wants. If they don't know,
# we offer some help
ap = argparse.ArgumentParser(prog='python -m hardwarelibrary')
ap.add_argument("-s", "--stellarnet", required=False, action='store_const',
                const=True, help="Decrypt the StellarnNet driver.  Contact StellarNet for info.")

args = vars(ap.parse_args())
decrypt = args['stellarnet']

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
        print('Cannot unzip stellarnet file')
