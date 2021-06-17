import unittest
import env
import struct
from hardwarelibrary.communication import SerialPort

class TestOptotune(unittest.TestCase):
    idVendor = 0x03eb
    idProduct = 0x2018
    port = None

# Test 1 : Verify is the port tty.usbmodem144201 exists and is detected genre. 
    def test01SerialPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.assertIsNotNone(self.port)
        self.port = None

# Test 2 : By using the function open(), is the port open? By using the function close(), is the port closed?
    def test02OpenPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.port.open(baudRate=115200)
        self.assertTrue(self.port.isOpen)
        self.port.close()
        self.assertFalse(self.port.isOpen)
        self.port = None

# Test 3 : By using the function open(), is the port open? By sending the command "Start", is the driver replying the right command "Ready\r\n"?
    def test03WriteStartCommandToPort(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.port.open(baudRate=115200)
        self.assertTrue(self.port.isOpen)

        command = 'Start'
        self.port.writeString(command)
        reply = self.port.readString()
        self.assertTrue(reply == 'Ready\r\n')

        self.port.close()
        self.port = None

# Calculates the crc for the optotune part 1 (create a table). Translated from C from https://static1.squarespace.com/static/5d9dde8d550f0a5f20b60b6a/t/601bc9aa063cc13aef894231/1612433909005/Optotune+Lens+Driver+4+manual.pdf
    def createCRCTable(self):
        # Create table
        length = 256
        table = [0]*length
        polynomial = 0xa001
        for i in range(length):
            value = 0
            temp = i
            for j in range(8):
                if (value ^ temp) & 0x0001 != 0:
                    value = (value >> 1) ^ polynomial
                else:
                    value = value >> 1
                temp = temp >> 1
            table[i] = value
        return table

# Test 6 : Is the table produced with the previous function is of 256 characters and not only zeros?
    def testTableCreation(self):
        table = self.createCRCTable()
        self.assertTrue(len(table) == 256)
        self.assertTrue(sum(table) != 0)

# Calculates the crc for the optotune part 2.
    def calculateCRC16bit(self, data) -> bytearray:
        """
        The C implementation is like this from the manual:
        ushort crc = 0; // initial CRC value
        for (int i = 0; i < bytes.Length; ++i) {
            byte index = (byte)(crc ^ bytes[i]);
            crc = (ushort)((crc >> 8) ^ table[index]);
        }
        """
        table = self.createCRCTable()

        crc = 0
        for byte in data:
            index = (crc ^ byte) & 0xff
            crc = (crc >> 8) ^ table[index]

        crcBytes = struct.pack('<H', crc)
        return bytearray(crcBytes)

# Test 7 :From documentation, we know that this is valid with the CRC at the end uint8_t data[] = { 0x41, 0x77, 0x04, 0xb2, 0x26, 0x93 } 
    def testValidateChecksum(self):
        data = bytearray(b'\x41\x77\x04\xb2')
        self.assertTrue(len(data) == 4)
        crc = self.calculateCRC16bit(data)
        self.assertEqual(crc[0], 0x26)
        self.assertEqual(crc[1], 0x93)

# Test 8 : Send a command AwxxLH to send a current to change the focal length of the lens. 
    def test04WriteSetCurrent(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.port.open(baudRate=115200)
        self.assertTrue(self.port.isOpen)

        dataSetCurrent = bytearray(b'Aw\x02\xbb')
        crc16 = self.calculateCRC16bit(dataSetCurrent)
        dataSetCurrent.extend(crc16)
        self.port.writeData(dataSetCurrent)
        self.port.close()
        self.port = None

# Test 9 : Verify the current in the driver. The default value should be 29284 (292.84mA).
    def test05WriteSetCurrent(self):
        self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
        self.port.open(baudRate=115200)
        self.assertTrue(self.port.isOpen)

        dataSetCurrent = bytearray(b'CrMA\x00\x00')
        crc16 = self.calculateCRC16bit(dataSetCurrent)
        dataSetCurrent.extend(crc16)
        self.port.writeData(dataSetCurrent)
        
        reply  = self.port.readData(length=9)
        print(reply)
        print(len(reply))
        unpackReply = struct.unpack('!ccchHcc', reply)
        self.assertTrue(len(reply) == 9)
        print(unpackReply)
        self.port.close()
        self.port = None

if __name__ == '__main__':
    unittest.main()
