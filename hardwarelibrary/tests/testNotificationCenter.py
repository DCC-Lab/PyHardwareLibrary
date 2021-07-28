import env # modifies path
import unittest
from hardwarelibrary.notificationcenter import NotificationCenter, Notification, ObserverInfo

class TestNotificationCenter(unittest.TestCase):
    def setUp(self):
        self.postedUserInfo = None
        self.notificationReceived = False

    def tearDown(self):
        NotificationCenter().clear()

    def testSingleton(self):
        self.assertIsNotNone(NotificationCenter())

    def testSingletonCanPost(self):
        NotificationCenter().postNotification("testNotification", self)

    def testAddObserver(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName="testNotification")

    def testAddObserverCount(self):
        nc = NotificationCenter()
        self.assertEqual(nc.observersCount(), 0)
        nc.addObserver(observer=self, method=self.handle, notificationName="testNotification")
        self.assertEqual(nc.observersCount(), 1)

    def testObserverInfo(self):
        nc = NotificationCenter()
        observer = ObserverInfo(observer=self, method=self.handle, notificationName="test", observedObject=nc)
        
        self.assertTrue(observer.matches(ObserverInfo(observer=self)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName="test")))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName=None)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName="test", observedObject=nc)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName=None, observedObject=nc)))

        self.assertFalse(observer.matches(ObserverInfo(observer=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notificationName="test", observedObject=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notificationName="other", observedObject=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notificationName="other", observedObject=None)))
        self.assertFalse(observer.matches(ObserverInfo(observer=self, notificationName="other", observedObject=None)))

    def testAddObserverRemoveObserver(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName="testNotification")
        self.assertEqual(nc.observersCount(), 1)
        nc.removeObserver(observer=self)
        self.assertEqual(nc.observersCount(), 0)

    def testRemoveMissingObserver(self):
        nc = NotificationCenter()
        self.assertEqual(nc.observersCount(), 0)
        NotificationCenter().removeObserver(self)
        self.assertEqual(nc.observersCount(), 0)

    def testAddObserverAnySenderAndPostithObject(self):
        nc = NotificationCenter()
        NotificationCenter().addObserver(observer=self, method=self.handle, notificationName="testNotification")
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self)
        self.assertTrue(self.notificationReceived)

        NotificationCenter().removeObserver(self)

    def testAddObserverAnySenderAndPostWithUserInfo(self):
        nc = NotificationCenter()
        NotificationCenter().addObserver(observer=self, method=self.handle, notificationName="testNotification")
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertTrue(self.notificationReceived)
        self.assertEqual(self.postedUserInfo, "1234")
        NotificationCenter().removeObserver(self)

    def testAddObserverWrongNotification(self):
        nc = NotificationCenter()
        NotificationCenter().addObserver(observer=self, method=self.handle, notificationName="testWrong")
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        NotificationCenter().removeObserver(self)

    def testAddObserverWrongSender(self):
        someObject = NotificationCenter()
        nc = NotificationCenter()
        NotificationCenter().addObserver(self, self.handle, "testNotification", someObject)
        NotificationCenter().postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        NotificationCenter().removeObserver(self)
        self.assertEqual(nc.observersCount(), 0)

    def testAddObserverNoDuplicates(self):
        nc = NotificationCenter()
        NotificationCenter().addObserver(self, self.handle, "testNotification", None)
        NotificationCenter().addObserver(self, self.handle, "testNotification", None)
        self.assertEqual(nc.observersCount(), 1)

    def testRemoveIncorrectObject(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        NotificationCenter().addObserver(self, self.handle, "testNotification", someObject)
        NotificationCenter().removeObserver(someObject)

    def handle(self, notification):
        self.notificationReceived = True
        # print("Received '{1}' from: {0}  with : {2}".format(notification.object, notification.name, notification.userInfo))
        self.postedUserInfo = notification.userInfo

if __name__ == '__main__':
    unittest.main()
