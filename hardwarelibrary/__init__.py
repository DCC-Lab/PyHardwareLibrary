__version__ = "1.0.0"
__author__ = "Daniel Cote <dccote@cervo.ulaval.ca>"

__all__ = ["communication","motion","oscilloscope","powermeters","spectrometers"]

# We want the modules at the top level
from .devicemanager import *

from hardwarelibrary.physicaldevice import *
from hardwarelibrary.notificationcenter import *
from hardwarelibrary.communication import *

# We want these modules in their namespace
import hardwarelibrary.spectrometers
import hardwarelibrary.oscilloscope
import hardwarelibrary.motion
import hardwarelibrary.cameras

#import sources #TODO: Not much to see here yet