"""Remotable device classes used by the remoting prototype and its tests.

These show the intended usage pattern -- mix Remotable into an existing device
class -- without modifying the core hierarchy. A real deployment would instead
add Remotable to PhysicalDevice (guarded so it is a no-op when Pyro5 is absent).
"""
from hardwarelibrary.motion.linearmotiondevice import DebugLinearMotionDevice
from hardwarelibrary.remoting.remotable import Remotable


class RemotableDebugStage(DebugLinearMotionDevice, Remotable):
    """A debug linear stage that can serve itself over Pyro5."""
