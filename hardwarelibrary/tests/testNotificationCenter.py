import env # modifies path
import unittest
from hardwarelibrary.notificationcenter import NotificationCenter, Notification

class TestNotificationCenter(unittest.TestCase):
    def setUp(self):
        self.postedUserInfo = None
        self.notificationReceived = False

    def testSingleton(self):
        self.assertIsNotNone(NotificationCenter())

    # def testSingletonCanPost(self):
    #     NotificationCenter().postNotification("testNotification", self)

    def testAddObserver(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, "testNotification", None)

    def testAddObserverAnySenderAndPost(self):
        NotificationCenter().addObserver(self, self.handle, "testNotification", None)
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=None)
        self.assertTrue(self.notificationReceived)

        NotificationCenter().removeObserver(self)

    def testAddObserverAnySenderAndPostithObject(self):
        NotificationCenter().addObserver(self, self.handle, "testNotification", None)
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self)
        self.assertTrue(self.notificationReceived)

        NotificationCenter().removeObserver(self)

    def testAddObserverAnySenderAndPostWithUserInfo(self):
        NotificationCenter().addObserver(self, self.handle, "testNotification", None)
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertTrue(self.notificationReceived)

        NotificationCenter().removeObserver(self)

    def testAddObserverWrongNotification(self):
        NotificationCenter().addObserver(self, self.handle, "testWrong", None)
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)

        NotificationCenter().removeObserver(self)

    def testAddObserverWrongSender(self):
        someObject = NotificationCenter()
        NotificationCenter().addObserver(self, self.handle, "testNotification", someObject)
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)

        NotificationCenter().removeObserver(self)

    def handle(self, notification):
        self.notificationReceived = True
        print("Received '{1}' from: {0}  with : {2}".format(notification.object, notification.name, notification.userInfo))
        self.postedUserInfo = None

if __name__ == '__main__':
    unittest.main()
