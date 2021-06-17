import unittest
import env
import struct
from hardwarelibrary.communication import SerialPort

class TestOptotune(unittest.TestCase):
    idVendor = 0x03eb
    idProduct = 0x2018
    port = None

    # def test01SerialPort(self):
    #     self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
    #     self.assertIsNotNone(self.port)
    #     self.port = None

    # def test02OpenPort(self):
    #     self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
    #     self.port.open(baudRate=115200)
    #     self.assertTrue(self.port.isOpen)
    #     self.port.close()
    #     self.assertFalse(self.port.isOpen)
    #     self.port = None

    # def test03WriteStartCommandToPort(self):
    #     self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
    #     self.port.open(baudRate=115200)
    #     self.assertTrue(self.port.isOpen)

    #     command = 'Start'
    #     self.port.writeString(command)
    #     reply = self.port.readString()
    #     self.assertTrue(reply == 'Ready\r\n')

    #     self.port.close()
    #     self.port = None

    def createCRCTable(self):
        # Create table, translated from C from https://static1.squarespace.com/static/5d9dde8d550f0a5f20b60b6a/t/601bc9aa063cc13aef894231/1612433909005/Optotune+Lens+Driver+4+manual.pdf
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

    def testTableCreation(self):
        table = self.createCRCTable()
        self.assertTrue(len(table) == 256)
        self.assertTrue(sum(table) != 0)

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

    def testValidateChecksum(self):
        # From documentation, we know that this is valid with the CRC at the end
        # uint8_t data[] = { 0x41, 0x77, 0x04, 0xb2, 0x26, 0x93 }
        data = bytearray(b'\x41\x77\x04\xb2')
        self.assertTrue(len(data) == 4)
        crc = self.calculateCRC16bit(data)
        self.assertEqual(crc[0], 0x26)
        self.assertEqual(crc[1], 0x93)

    # def test04WriteSetCurrent(self):
    #     self.port = SerialPort(bsdPath='/dev/tty.usbmodem144201')
    #     self.port.open(baudRate=115200)
    #     self.assertTrue(self.port.isOpen)

    #     dataSetCurrent = bytearray(b'Aw\x02\xbb')
    #     crc16 = self.calculateCRC16bit(dataSetCurrent)
    #     dataSetCurrent.extend(crc16)
    #     self.port.writeData(dataSetCurrent)
    #     error = self.port.readString()
    #     self.assertTrue(error[0] == 'E')
    #     self.assertTrue(error[1] == '1')
    #     self.assertTrue(len(error) >= 5)
    #     self.port.close()
    #     self.port = None


if __name__ == '__main__':
    unittest.main()
