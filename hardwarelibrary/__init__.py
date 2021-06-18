__version__ = "0.9.4"
__author__ = "Daniel Cote <dccote@cervo.ulaval.ca>"

__all__ = ["communication", "spectrometers"]

# We want the modules at the top level
from hardwarelibrary.physicaldevice import *
from hardwarelibrary.communication import *

# We want these modules in their namespace
import hardwarelibrary.spectrometers
import hardwarelibrary.motion

#import sources #TODO: Not much to see here yet