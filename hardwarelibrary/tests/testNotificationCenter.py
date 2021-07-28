import env # modifies path
import unittest
from hardwarelibrary.notificationcenter import NotificationCenter

class TestNotificationCenter(unittest.TestCase):
    def testSingleton(self):
        self.assertIsNotNone(NotificationCenter())

    def testSingletonCanPost(self):
        NotificationCenter().postNotification("testNotification", self, userInfo=None)

    def testAddObserver(self):
        NotificationCenter().addObserver(self, self.handle, "testNotification", None)
        NotificationCenter().postNotification("testNotification", self, userInfo=None)
        NotificationCenter().removeObserver(self)

    def handle(self, sender, with_name, with_info):
        print("Received '{1}' from: {0}  with : {2}".format(sender, with_name, with_info))

if __name__ == '__main__':
    unittest.main()
