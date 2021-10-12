import time
from enum import Enum
from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
import cv2


class UVCCamera(PhysicalDevice):
    classIdVendor = 0x05ac
    classIdProduct = 0x1112
    def __init__(self, serialNumber:str = None, idProduct:int = None, idVendor:int = None):
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""
        self.cameraHandler = None

    def doInitializeDevice(self):
        # Open the first camera we find
        self.cameraHandler = cv2.VideoCapture(0)

        if self.cameraHandler is None:
            raise Exception("Could not open video device")

        if not (self.cameraHandler.isOpened()):
            raise Exception("Could not open video device")

    def doShutdownDevice(self):
        self.cameraHandler.release()
        self.cameraHandler.destroyAllWindows()

    def capture(self):
        while (True):
            # Capture frame-by-frame
            ret, frame = self.cameraHandler.read()
            # Display the resulting frame
            cv2.imshow('preview', frame)
            # Waits for a user input to quit the application
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

if __name__ == "__main__":
    cam = Camera()
    cam.initializeDevice()
    cam.capture()