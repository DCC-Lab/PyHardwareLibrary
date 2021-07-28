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
        nc = NotificationCenter()
        nc.postNotification("testNotification", self)

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
        nc.removeObserver(self)
        self.assertEqual(nc.observersCount(), 0)

    def testAddObserverAnySenderAndPostithObject(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName="testNotification")
        nc.postNotification(notificationName="testNotification", notifyingObject=self)
        self.assertTrue(self.notificationReceived)

        nc.removeObserver(self)

    def testAddObserverAnySenderAndPostWithUserInfo(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName="testNotification")
        nc.postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertTrue(self.notificationReceived)
        self.assertEqual(self.postedUserInfo, "1234")
        nc.removeObserver(self)

    def testAddObserverWrongNotification(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName="testWrong")
        nc.postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        nc.removeObserver(self)

    def testAddObserverWrongSender(self):
        someObject = NotificationCenter()
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, "testNotification", someObject)
        nc.postNotification(notificationName="testNotification", notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        nc.removeObserver(self)
        self.assertEqual(nc.observersCount(), 0)

    def testAddObserverNoDuplicates(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, "testNotification", None)
        nc.addObserver(self, self.handle, "testNotification", None)
        self.assertEqual(nc.observersCount(), 1)

    def testAddObserverNoDuplicates2(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, "testNotification", None)
        nc.addObserver(self, self.handle, "testNotification2", None)
        self.assertEqual(nc.observersCount(), 2)

    def testAddObserverNoDuplicates3(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, "testNotification", None)
        nc.addObserver(self, self.handle, "testNotification", nc)
        self.assertEqual(nc.observersCount(), 1)

    def testRemoveIncorrectObject(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        nc.addObserver(self, self.handle, "testNotification", someObject)
        nc.removeObserver(someObject)
        self.assertEqual(nc.observersCount(), 1)

    def handle(self, notification):
        self.notificationReceived = True
        self.postedUserInfo = notification.userInfo

if __name__ == '__main__':
    unittest.main()
