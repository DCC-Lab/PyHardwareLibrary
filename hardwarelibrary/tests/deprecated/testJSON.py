import json
import unittest

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
