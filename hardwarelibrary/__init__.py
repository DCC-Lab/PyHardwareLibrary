__version__ = "0.9.2"
__author__ = "Daniel Cote <dccote@cervo.ulaval.ca>"

__all__ = ["communication", "spectrometers"]

from hardwarelibrary.physicaldevice import *
from hardwarelibrary.communication import *

import hardwarelibrary.spectrometers

#import motion #TODO: Not ready
#import sources #TODO: Not much to see here yet