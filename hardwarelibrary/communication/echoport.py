import time
import random

from hardwarelibrary.communication import *
from threading import Thread, Lock

class DebugEchoPort(DebugPort):
    def __init__(self, delay=0):
        super(DebugEchoPort, self).__init__(delay=delay)

