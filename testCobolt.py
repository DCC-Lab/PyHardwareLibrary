import json
import unittest
from serial import *
from CommunicationPort import *
import time
from threading import Thread, Lock

class TestJSON(unittest.TestCase):
    def testOpenFile(self):
        with open('cobolt.json') as json_file:  
            data = json.load(json_file)
            for command in data:
                print('Name: ' + command['name'])
                print('Pattern: ' + command['pattern'])
                print('')

if __name__ == '__main__':
    unittest.main()
