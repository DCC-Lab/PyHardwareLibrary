from hardwarelibrary.communication import *

# dev = USBDeviceDescription("Optotune LD", idVendor=0x03eb, idProduct=0x2018)
# dev.regexPOSIXPort = r"cu.usbmodem\d{6}"
# dev.usbParameters = USBParameters(configuration=0, 
#                                   interface=1,
#                                   alternate=0,
#                                   outputEndpoint=0,
#                                   inputEndpoint=1)
# dev.mustAssertTrue = ['isVisible', 'isVisibleOnUSBHub','isVisibleAsPOSIXPort',
#                       'isValidPOSIXPath','posixPortCanBeOpened', 'hasUniquePOSIXPortMatch', 
#                       'usbPortCanBeOpened', 'canReadWritePOSIXCommands',
#                       'canReadWriteUSBCommands']
# dev.mustAssertFalse = []

# dev.deviceCommands.append(DeviceCommand(text='Start',reply='Ready\r\n'))
# dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd'))
# #    dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd', replyData='\x00'))

# #dev.usbPort.open()
# # print(dev.__dict__)
# dev.diagnoseConnectivity()
# #    dev.report()

for dev in USBDeviceDescription.connectedUSBDevices(idVendor=0x2457):
	print(dev)

dev = USBDeviceDescription("Ocean Optics USB2000", idVendor=0x2457, idProduct=0x1002)
# dev.regexPOSIXPort = r"cu.usbmodem\d{6}"
dev.usbParameters = USBParameters(configuration=1, 
                                  interface=0,
                                  alternate=0,
                                  outputEndpoint=0,
                                  inputEndpoint=1)
dev.mustAssertTrue = ['isVisible', 'isVisibleOnUSBHub', 
                      'usbPortCanBeOpened',
                      'canReadWriteUSBCommands']
dev.mustAssertFalse = ['isVisibleAsPOSIXPort','isValidPOSIXPath',
'canReadWritePOSIXCommands', 'posixPortCanBeOpened', 'hasUniquePOSIXPortMatch']

dev.deviceCommands.append(DeviceCommand(data=b'\x01',replyData=None))
dev.deviceCommands.append(DeviceCommand(data=b'\x05',replyData=b"1234567"))
# dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd'))
#    dev.deviceCommands.append(DeviceCommand(data=b'\x50\x77\x44\x41\x07\xd0\x00\x00\x31\xfd', replyData='\x00'))
# print(dev.isVisibleOnUSBHub)
dev.report()
#dev.usbPort.open()
# print(dev.__dict__)
# dev.diagnoseConnectivity()
