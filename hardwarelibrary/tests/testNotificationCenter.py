import env
import unittest
from enum import Enum

from notificationcenter import NotificationCenter, ObserverInfo


class NotificationNameTest(Enum):
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
        nc.post_notification(NotificationNameTest.test, self)

    def testAddObserver(self):
        nc = NotificationCenter()
        nc.add_observer(observer=self, method=self.handle, notification_name=NotificationNameTest.test)

    def testAddObserverCount(self):
        nc = NotificationCenter()
        self.assertEqual(nc.observers_count(), 0)
        nc.add_observer(observer=self, method=self.handle, notification_name=NotificationNameTest.test)
        self.assertEqual(nc.observers_count(), 1)

    def testObserverInfo(self):
        nc = NotificationCenter()
        observer = ObserverInfo(observer=self, method=self.handle, notification_name=NotificationNameTest.test, observed_object=nc)
        
        self.assertTrue(observer.matches(ObserverInfo(observer=self)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notification_name=NotificationNameTest.test)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notification_name=None)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notification_name=NotificationNameTest.test, observed_object=nc)))
        self.assertTrue(observer.matches(ObserverInfo(observer=self, notification_name=None, observed_object=nc)))

        self.assertFalse(observer.matches(ObserverInfo(observer=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notification_name=NotificationNameTest.test, observed_object=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notification_name=NotificationNameTest.other, observed_object=nc)))
        self.assertFalse(observer.matches(ObserverInfo(observer=nc, notification_name=NotificationNameTest.other, observed_object=None)))
        self.assertFalse(observer.matches(ObserverInfo(observer=self, notification_name=NotificationNameTest.other, observed_object=None)))

    def testAddObserverRemoveObserver(self):
        nc = NotificationCenter()
        nc.add_observer(observer=self, method=self.handle, notification_name=NotificationNameTest.test)
        self.assertEqual(nc.observers_count(), 1)
        nc.remove_observer(observer=self)
        self.assertEqual(nc.observers_count(), 0)

    def testRemoveMissingObserver(self):
        nc = NotificationCenter()
        self.assertEqual(nc.observers_count(), 0)
        nc.remove_observer(self)
        self.assertEqual(nc.observers_count(), 0)

    def testAddObserverAnySenderAndPostithObject(self):
        nc = NotificationCenter()
        nc.add_observer(observer=self, method=self.handle, notification_name=NotificationNameTest.test)
        nc.post_notification(notification_name=NotificationNameTest.test, notifying_object=self)
        self.assertTrue(self.notificationReceived)

        nc.remove_observer(self)

    def testAddObserverAnySenderAndPostWithUserInfo(self):
        nc = NotificationCenter()
        nc.add_observer(observer=self, method=self.handle, notification_name=NotificationNameTest.test)
        nc.post_notification(notification_name=NotificationNameTest.test, notifying_object=self, user_info="1234")
        self.assertTrue(self.notificationReceived)
        self.assertEqual(self.postedUserInfo, "1234")
        nc.remove_observer(self)

    def testAddObserverWrongNotification(self):
        nc = NotificationCenter()
        nc.add_observer(observer=self, method=self.handle, notification_name=NotificationNameTest.wrong)
        nc.post_notification(notification_name=NotificationNameTest.test, notifying_object=self, user_info="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        nc.remove_observer(self)

    def testAddObserverWrongSender(self):
        someObject = NotificationCenter()
        nc = NotificationCenter()
        nc.add_observer(self, method=self.handle, notification_name=NotificationNameTest.test, observed_object=someObject)
        nc.post_notification(notification_name=NotificationNameTest.test, notifying_object=self, user_info="1234")
        self.assertFalse(self.notificationReceived)
        self.assertNotEqual(self.postedUserInfo, "1234")
        nc.remove_observer(self)
        self.assertEqual(nc.observers_count(), 0)

    def testAddObserverNoDuplicates(self):
        nc = NotificationCenter()
        nc.add_observer(self, self.handle, NotificationNameTest.test, None)
        nc.add_observer(self, self.handle, NotificationNameTest.test, None)
        self.assertEqual(nc.observers_count(), 1)

    def testAddObserverNoDuplicates2(self):
        nc = NotificationCenter()
        nc.add_observer(self, self.handle, NotificationNameTest.test, None)
        nc.add_observer(self, self.handle, NotificationNameTest.test2, None)
        self.assertEqual(nc.observers_count(), 2)

    def testAddObserverNoDuplicates3(self):
        nc = NotificationCenter()
        nc.add_observer(self, self.handle, NotificationNameTest.test, None)
        nc.add_observer(self, self.handle, NotificationNameTest.test, nc)
        self.assertEqual(nc.observers_count(), 1)

    def testRemoveIncorrectObject(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        nc.add_observer(self, self.handle, NotificationNameTest.test, someObject)
        nc.remove_observer(someObject)
        self.assertEqual(nc.observers_count(), 1)

    def testRemoveManyObservers(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        nc.add_observer(self, self.handle, NotificationNameTest.test, someObject)
        nc.add_observer(self, self.handle, NotificationNameTest.test2, someObject)
        nc.add_observer(self, self.handle, NotificationNameTest.test3, someObject)
        nc.add_observer(self, self.handle, NotificationNameTest.test4, None)
        nc.remove_observer(self)
        self.assertEqual(nc.observers_count(), 0)

    def testRemoveManyObservers2(self):
        nc = NotificationCenter()
        someObject = NotificationCenter()
        nc.add_observer(self, self.handle, NotificationNameTest.test, someObject)
        nc.add_observer(self, self.handle, NotificationNameTest.test2, someObject)
        nc.add_observer(self, self.handle, NotificationNameTest.test3, someObject)
        nc.add_observer(self, self.handle, NotificationNameTest.test4, None)
        nc.remove_observer(self, observed_object=someObject)
        self.assertEqual(nc.observers_count(), 0)

    def handle(self, notification):
        self.notificationReceived = True
        self.postedUserInfo = notification.user_info

if __name__ == '__main__':
    unittest.main()
