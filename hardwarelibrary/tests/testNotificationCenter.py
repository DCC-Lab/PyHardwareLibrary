import env
import unittest
from enum import Enum

from hardwarelibrary.notificationcenter import NotificationCenter, ObserverInfo


class TestNotificationName(Enum):
    test       = "test"
    test2      = "test2"
    test3      = "test3"
    test4      = "test4"
    other      = "other"
    wrong      = "wrong"

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
        nc.postNotification(TestNotificationName.test, self)

    def testAddObserver(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName=TestNotificationName.test)

    def testAddObserverCount(self):
        nc = NotificationCenter()
        self.assertEqual(nc.observersCount(), 0)
        nc.addObserver(observer=self, method=self.handle, notificationName=TestNotificationName.test)
        self.assertEqual(nc.observersCount(), 1)

    def testObserverInfo(self):
        nc = NotificationCenter()
        observer = ObserverInfo(observer=self, method=self.handle, notificationName=TestNotificationName.test, observedObject=nc)
        
        self.assertTrue(observer.matches(ObserverInfo(observer=self)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName=TestNotificationName.test)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName=None)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName=TestNotificationName.test, observedObject=nc)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notificationName=None, observedObject=nc)))

        self.assertFalse(observer.matches(ObserverInfo(observer=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notificationName=TestNotificationName.test, observedObject=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notificationName=TestNotificationName.other, observedObject=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notificationName=TestNotificationName.other, observedObject=None)))
        self.assertFalse(observer.matches(ObserverInfo(observer=self, notificationName=TestNotificationName.other, observedObject=None)))

    def testAddObserverRemoveObserver(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName=TestNotificationName.test)
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
        nc.addObserver(observer=self, method=self.handle, notificationName=TestNotificationName.test)
        nc.postNotification(notificationName=TestNotificationName.test, notifyingObject=self)
        self.assertTrue(self.notificationReceived)

        nc.removeObserver(self)

    def testAddObserverAnySenderAndPostWithUserInfo(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName=TestNotificationName.test)
        nc.postNotification(notificationName=TestNotificationName.test, notifyingObject=self, userInfo="1234")
        self.assertTrue(self.notificationReceived)
        self.assertEqual(self.postedUserInfo, "1234")
        nc.removeObserver(self)

    def testAddObserverWrongNotification(self):
        nc = NotificationCenter()
        nc.addObserver(observer=self, method=self.handle, notificationName=TestNotificationName.wrong)
        nc.postNotification(notificationName=TestNotificationName.test, notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        nc.removeObserver(self)

    def testAddObserverWrongSender(self):
        someObject = NotificationCenter()
        nc = NotificationCenter()
        nc.addObserver(self, method=self.handle, notificationName=TestNotificationName.test, observedObject=someObject)
        nc.postNotification(notificationName=TestNotificationName.test, notifyingObject=self, userInfo="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        nc.removeObserver(self)
        self.assertEqual(nc.observersCount(), 0)

    def testAddObserverNoDuplicates(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, TestNotificationName.test, None)
        nc.addObserver(self, self.handle, TestNotificationName.test, None)
        self.assertEqual(nc.observersCount(), 1)

    def testAddObserverNoDuplicates2(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, TestNotificationName.test, None)
        nc.addObserver(self, self.handle, TestNotificationName.test2, None)
        self.assertEqual(nc.observersCount(), 2)

    def testAddObserverNoDuplicates3(self):
        nc = NotificationCenter()
        nc.addObserver(self, self.handle, TestNotificationName.test, None)
        nc.addObserver(self, self.handle, TestNotificationName.test, nc)
        self.assertEqual(nc.observersCount(), 1)

    def testRemoveIncorrectObject(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        nc.addObserver(self, self.handle, TestNotificationName.test, someObject)
        nc.removeObserver(someObject)
        self.assertEqual(nc.observersCount(), 1)

    def testRemoveManyObservers(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        nc.addObserver(self, self.handle, TestNotificationName.test, someObject)
        nc.addObserver(self, self.handle, TestNotificationName.test2, someObject)
        nc.addObserver(self, self.handle, TestNotificationName.test3, someObject)
        nc.addObserver(self, self.handle, TestNotificationName.test4, None)
        nc.removeObserver(self)
        self.assertEqual(nc.observersCount(), 0)

    def testRemoveManyObservers2(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        nc.addObserver(self, self.handle, TestNotificationName.test, someObject)
        nc.addObserver(self, self.handle, TestNotificationName.test2, someObject)
        nc.addObserver(self, self.handle, TestNotificationName.test3, someObject)
        nc.addObserver(self, self.handle, TestNotificationName.test4, None)
        nc.removeObserver(self, observedObject=someObject)
        self.assertEqual(nc.observersCount(), 0)

    def handle(self, notification):
        self.notificationReceived = True
        self.postedUserInfo = notification.userInfo

if __name__ == '__main__':
    unittest.main()
