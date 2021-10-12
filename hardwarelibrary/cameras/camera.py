import time
from enum import Enum
from hardwarelibrary.physicaldevice import PhysicalDevice
from hardwarelibrary.notificationcenter import NotificationCenter, Notification
from threading import Thread, RLock
import cv2


class CameraDeviceNotification(Enum):
    willStartCapture    = "willStartCapture"
    didStartCapture     = "didStartCapture"
    willStoptCapture    = "willStopCapture"
    didStopCapture      = "didStopCapture"
    imageCaptured       = "imageCaptured"

class FaceTimeCamera(PhysicalDevice):
    classIdVendor = 0x05ac
    classIdProduct = 0x1112
    def __init__(self, serialNumber:str = None, idProduct:int = None, idVendor:int = None):
        super().__init__(serialNumber, idProduct, idVendor)
        self.version = ""
        self.cameraHandler = None
        self.quitLoop = False
        self.lock = RLock()

    def doInitializeDevice(self):
        with self.lock:
            # FIXME: Open the first camera we find
            self.cameraHandler = cv2.VideoCapture(0)

            if self.cameraHandler is None:
                raise Exception("Could not open video device")

            if not (self.cameraHandler.isOpened()):
                raise Exception("Could not open video device")

    def doShutdownDevice(self):
        with self.lock:
            self.cameraHandler.release()
            self.cameraHandler.destroyAllWindows()

    def livePreview(self):
        self.captureLoopSynchronous()

    def start(self):
        with self.lock:
            if not self.isMonitoring:
                self.quitLoop = False
                self.mainLoop = Thread(target=self.captureLoop, name="Camera-CaptureLoop")
                NotificationCenter().postNotification(notificationName=CameraDeviceNotification.willStartCapture, notifyingObject=self)
                self.mainLoop.start()
            else:
                raise RuntimeError("Monitoring loop already running")

    @property
    def isCapturing(self):
        return self.mainLoop is not None

    def stop(self):
        if self.isCapturing:
            NotificationCenter().postNotification(CameraDeviceNotification.willStoptCapture, notifyingObject=self)
            with self.lock:
                self.quitLoop = True
            self.mainLoop.join()
            self.mainLoop = None
            NotificationCenter().postNotification(CameraDeviceNotification.didStopCapture, notifyingObject=self)
        else:
            raise RuntimeError("No monitoring loop running")

    def captureLoopSynchronous(self):
        frame = None
        while (True):
            NotificationCenter().postNotification(notificationName=CameraDeviceNotification.didStartCapture, notifyingObject=self)
            frame = self.doCaptureFrame()
            NotificationCenter().postNotification(CameraDeviceNotification.imageCaptured, self, frame)

            cv2.imshow('Preview (Q to quit)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    def captureLoopThread(self):
        frame = None
        while (True):
            NotificationCenter().postNotification(notificationName=CameraDeviceNotification.didStartCapture, notifyingObject=self)
            frame = self.doCaptureFrame()
            NotificationCenter().postNotification(CameraDeviceNotification.imageCaptured, self, frame)

            if self.quitLoop:
                return

    def doCaptureFrame(self):
        with self.lock:
            # Capture frame-by-frame
            ret, frame = self.cameraHandler.read()
            return frame

if __name__ == "__main__":
    cam = FaceTimeCamera()
    cam.initializeDevice()
    cam.livePreview()
