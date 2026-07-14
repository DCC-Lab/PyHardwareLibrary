Core
====

The foundational classes shared by every device: the abstract base class,
the discovery singleton, and the notification system.

PhysicalDevice
--------------

.. automodule:: hardwarelibrary.physicaldevice

Capabilities
------------

Interface-segregated capability mixins shared by every device family. Each
subclasses the single ``Capability`` base; ``PhysicalDevice`` introspects them
through ``capabilities()`` / ``hasCapability()``.

.. automodule:: hardwarelibrary.capabilities

DeviceManager
-------------

.. automodule:: hardwarelibrary.devicemanager

NotificationCenter
------------------

.. automodule:: hardwarelibrary.notificationcenter

EchoDevice
----------

.. automodule:: hardwarelibrary.echodevice

Utilities
---------

.. automodule:: hardwarelibrary.utils
