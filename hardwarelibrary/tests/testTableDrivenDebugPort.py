import env
import unittest
from struct import pack, unpack

from hardwarelibrary.communication.debugport import (
    TableDrivenDebugPort, BinaryCommandEntry, TextCommandEntry
)


class BinaryFixture(TableDrivenDebugPort):
    def __init__(self):
        super().__init__()
        self.value = 0
        self.binary_commands = [
            BinaryCommandEntry(name='set', prefix=b'S', request_format='<xl'),
            BinaryCommandEntry(name='get', prefix=b'G', response_format='<cl'),
        ]

    def process_command(self, name, params, endPointIndex):
        if name == 'set':
            self.value = params[0]
            return b'\r'
        elif name == 'get':
            return (b'g', self.value)


class TextFixture(TableDrivenDebugPort):
    def __init__(self):
        super().__init__()
        self.registers = {}
        self.text_commands = [
            TextCommandEntry(name='set', pattern=r'SET (\w+) (-?\d+)\r'),
            TextCommandEntry(name='get', pattern=r'GET (\w+)\r',
                             response='VAL {0}\r'),
        ]

    def process_command(self, name, params, endPointIndex):
        if name == 'set':
            key, value = params
            self.registers[key] = int(value)
            return "OK\r"
        elif name == 'get':
            key = params[0]
            return (str(self.registers.get(key, 0)),)


class MixedFixture(TableDrivenDebugPort):
    def __init__(self):
        super().__init__()
        self.state = 0
        self.binary_commands = [
            BinaryCommandEntry(name='bin_set', prefix=b'\x01', request_format='<xl'),
        ]
        self.text_commands = [
            TextCommandEntry(name='text_get', pattern=r'GET\r'),
        ]

    def process_command(self, name, params, endPointIndex):
        if name == 'bin_set':
            self.state = params[0]
            return b'\x06'
        elif name == 'text_get':
            return "V {}\r".format(self.state)


class TestBinaryDispatch(unittest.TestCase):
    def setUp(self):
        self.port = BinaryFixture()
        self.port.open()

    def tearDown(self):
        self.port.close()

    def testSetCommand(self):
        payload = pack('<cl', b'S', 42)
        self.port.writeData(payload)
        self.assertEqual(self.port.readData(1), b'\r')
        self.assertEqual(self.port.value, 42)

    def testGetCommand(self):
        self.port.value = 99
        self.port.writeData(b'G')
        data = self.port.readData(5)
        tag, val = unpack('<cl', data)
        self.assertEqual(tag, b'g')
        self.assertEqual(val, 99)

    def testSetThenGet(self):
        payload = pack('<cl', b'S', 123)
        self.port.writeData(payload)
        self.port.readData(1)

        self.port.writeData(b'g')
        data = self.port.readData(5)
        _, val = unpack('<cl', data)
        self.assertEqual(val, 123)

    def testCaseInsensitivePrefix(self):
        payload = pack('<cl', b's', 7)
        self.port.writeData(payload)
        self.assertEqual(self.port.readData(1), b'\r')
        self.assertEqual(self.port.value, 7)


class TestTextDispatch(unittest.TestCase):
    def setUp(self):
        self.port = TextFixture()
        self.port.open()

    def tearDown(self):
        self.port.close()

    def testSetCommand(self):
        self.port.writeData(b'SET foo 42\r')
        reply = self.port.readData(3)
        self.assertEqual(reply, b'OK\r')
        self.assertEqual(self.port.registers['foo'], 42)

    def testGetCommand(self):
        self.port.registers['bar'] = 99
        self.port.writeData(b'GET bar\r')
        reply = self.port.readData(7)
        self.assertEqual(reply, b'VAL 99\r')

    def testSetThenGet(self):
        self.port.writeData(b'SET x 55\r')
        self.port.readData(3)

        self.port.writeData(b'GET x\r')
        reply = self.port.readData(7)
        self.assertEqual(reply, b'VAL 55\r')

    def testNegativeValue(self):
        self.port.writeData(b'SET neg -10\r')
        reply = self.port.readData(3)
        self.assertEqual(reply, b'OK\r')
        self.assertEqual(self.port.registers['neg'], -10)


class TestMixedDispatch(unittest.TestCase):
    def setUp(self):
        self.port = MixedFixture()
        self.port.open()

    def tearDown(self):
        self.port.close()

    def testBinaryThenText(self):
        payload = pack('<cl', b'\x01', 77)
        self.port.writeData(payload)
        self.assertEqual(self.port.readData(1), b'\x06')

        self.port.writeData(b'GET\r')
        reply = self.port.readData(5)
        self.assertEqual(reply, b'V 77\r')

    def testBinaryPreferredOverText(self):
        """Binary commands are checked first."""
        payload = pack('<cl', b'\x01', 1)
        self.port.writeData(payload)
        self.assertEqual(self.port.readData(1), b'\x06')


class TestUnrecognizedCommand(unittest.TestCase):
    def setUp(self):
        self.port = BinaryFixture()
        self.port.open()

    def tearDown(self):
        self.port.close()

    def testUnrecognizedProducesNoOutput(self):
        self.port.writeData(b'Z')
        self.assertEqual(self.port.bytesAvailable(), 0)


class TestNoneResponse(unittest.TestCase):
    """When process_command returns None, no auto-response is written."""

    def setUp(self):
        port = TableDrivenDebugPort()
        port.binary_commands = [
            BinaryCommandEntry(name='silent', prefix=b'X'),
        ]
        port.process_command = lambda name, params, ep: None
        self.port = port
        self.port.open()

    def tearDown(self):
        self.port.close()

    def testNoneResponseWritesNothing(self):
        self.port.writeData(b'X')
        self.assertEqual(self.port.bytesAvailable(), 0)


if __name__ == '__main__':
    unittest.main()
