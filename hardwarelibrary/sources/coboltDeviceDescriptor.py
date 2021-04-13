r"""
    Obtained from Windows with software like USBView - Daniel Cote
    
        =========================== USB Port8 ===========================

    Connection Status        : 0x01 (Device is connected)
    Port Chain               : 3-8

          ======================== USB Device ========================

            +++++++++++++++++ Device Information ++++++++++++++++++
    Friendly Name            : Cobolt Laser (COM7)
    Device Description       : Cobolt Laser
    Device Path              : \\?\usb#vid_25dc&pid_0006#000013245678#{a5dcbf10-6530-11d2-901f-00c04fb951ed}
    Device ID                : USB\VID_25DC&PID_0006\000013245678
    Hardware IDs             : USB\VID_25DC&PID_0006&REV_0100 USB\VID_25DC&PID_0006
    Driver KeyName           : {4d36e978-e325-11ce-bfc1-08002be10318}\0006 (GUID_DEVCLASS_PORTS)
    Driver                   : system32\DRIVERS\usbser.sys (Version: 6.1.7601.18247  Date: 2013-08-28)
    Driver Inf               : C:\Windows\inf\oem107.inf
    Legacy BusType           : PNPBus
    Class                    : Ports
    Class GUID               : {4d36e978-e325-11ce-bfc1-08002be10318} (GUID_DEVCLASS_PORTS)
    Interface GUID           : {a5dcbf10-6530-11d2-901f-00c04fb951ed} (GUID_DEVINTERFACE_USB_DEVICE)
    Service                  : usbser
    Enumerator               : USB
    Location Info            : Port_#0008.Hub_#0001
    Location IDs             : PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(8)
    Container ID             : {1ddbadd3-ec62-5d3a-a00a-64685c39b2e8}
    Manufacturer Info        : Cobolt AB
    Capabilities             : 0x94 (Removable, UniqueID, SurpriseRemovalOK)
    Status                   : 0x0180600A (DN_DRIVER_LOADED, DN_STARTED, DN_DISABLEABLE, DN_REMOVABLE, DN_NT_ENUMERATOR, DN_NT_DRIVER)
    Problem Code             : 0
    Power State              : D0 (supported: D0, D3, wake from D0)
    COM-Port                 : COM7 (\Device\USBSER000)

            +++++++++++++++++ Registry USB Flags +++++++++++++++++
    HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\UsbFlags\25DC00060100
     osvc                    : REG_BINARY 00 00
     SkipContainerIdQuery    : REG_BINARY 01 00 00 00

            ---------------- Connection Information ---------------
    Connection Index         : 0x08 (8)
    Connection Status        : 0x01 (DeviceConnected)
    Current Config Value     : 0x01
    Device Address           : 0x0B (11)
    Is Hub                   : 0x00 (no)
    Number Of Open Pipes     : 0x03 (3)
    Device Bus Speed         : 0x01 (Full-Speed)
    Pipe0ScheduleOffset      : 0x00 (0)
    Pipe1ScheduleOffset      : 0x00 (0)
    Pipe2ScheduleOffset      : 0x00 (0)
    Data (HexDump)           : 08 00 00 00 12 01 00 02 02 00 00 08 DC 25 06 00   .............%..
                               00 01 01 02 03 01 01 01 00 0B 00 03 00 00 00 01   ................
                               00 00 00 07 05 82 03 40 00 08 00 00 00 00 07 05   .......@........
                               01 02 40 00 01 00 00 00 00 07 05 81 02 40 00 01   ..@..........@..
                               00 00 00 00                                       ....

        ---------------------- Device Descriptor ----------------------
    bLength                  : 0x12 (18 bytes)
    bDescriptorType          : 0x01 (Device Descriptor)
    bcdUSB                   : 0x200 (USB Version 2.00)
    bDeviceClass             : 0x02 (Communications and CDC Control)
    bDeviceSubClass          : 0x00
    bDeviceProtocol          : 0x00 (No class specific protocol required)
    bMaxPacketSize0          : 0x08 (8 bytes)
    idVendor                 : 0x25DC
    idProduct                : 0x0006
    bcdDevice                : 0x0100
    iManufacturer            : 0x01 (String Descriptor 1)
     Language 0x0409         : "Cobolt AB"
    iProduct                 : 0x02 (String Descriptor 2)
     Language 0x0409         : "Cobolt Laser Driver MLD"
    iSerialNumber            : 0x03 (String Descriptor 3)
     Language 0x0409         : "000013245678"
    bNumConfigurations       : 0x01 (1 Configuration)
    Data (HexDump)           : 12 01 00 02 02 00 00 08 DC 25 06 00 00 01 01 02   .........%......
                               03 01                                             ..

        ------------------ Configuration Descriptor -------------------
    bLength                  : 0x09 (9 bytes)
    bDescriptorType          : 0x02 (Configuration Descriptor)
    wTotalLength             : 0x0043 (67 bytes)
    bNumInterfaces           : 0x02 (2 Interfaces)
    bConfigurationValue      : 0x01 (Configuration 1)
    iConfiguration           : 0x00 (No String Descriptor)
    bmAttributes             : 0x80
     D7: Reserved, set 1     : 0x01
     D6: Self Powered        : 0x00 (no)
     D5: Remote Wakeup       : 0x00 (no)
     D4..0: Reserved, set 0  : 0x00
    MaxPower                 : 0x32 (100 mA)
    Data (HexDump)           : 09 02 43 00 02 01 00 80 32 09 04 00 00 01 02 02   ..C.....2.......
                               01 00 05 24 00 10 01 05 24 01 01 01 04 24 02 06   ...$....$....$..
                               05 24 06 00 01 07 05 82 03 40 00 08 09 04 01 00   .$.......@......
                               02 0A 00 00 00 07 05 01 02 40 00 01 07 05 81 02   .........@......
                               40 00 01                                          @..

            ---------------- Interface Descriptor -----------------
    bLength                  : 0x09 (9 bytes)
    bDescriptorType          : 0x04 (Interface Descriptor)
    bInterfaceNumber         : 0x00
    bAlternateSetting        : 0x00
    bNumEndpoints            : 0x01 (1 Endpoint)
    bInterfaceClass          : 0x02 (Communications and CDC Control)
    bInterfaceSubClass       : 0x02 (Abstract Control Model)
    bInterfaceProtocol       : 0x01 (AT Commands defined by ITU-T V.250 etc)
    iInterface               : 0x00 (No String Descriptor)
    Data (HexDump)           : 09 04 00 00 01 02 02 01 00                        .........

            -------------- CDC Interface Descriptor ---------------
    bFunctionLength          : 0x05 (5 bytes)
    bDescriptorType          : 0x24 (Interface)
    bDescriptorSubType       : 0x00 (Header Functional Descriptor)
    bcdCDC                   : 0x110 (CDC Version 1.10)
    Data (HexDump)           : 05 24 00 10 01                                    .$...

            -------------- CDC Interface Descriptor ---------------
    bFunctionLength          : 0x05 (5 bytes)
    bDescriptorType          : 0x24 (Interface)
    bDescriptorSubType       : 0x01 (Call Management Functional Descriptor)
    bmCapabilities           : 0x01
     D7..2:                  : 0x00 (Reserved)
     D1   :                  : 0x00 (sends/receives call management information only over the Communication Class interface)
     D0   :                  : 0x01 (handles call management itself)
    bDataInterface           : 0x01
    Data (HexDump)           : 05 24 01 01 01                                    .$...

            -------------- CDC Interface Descriptor ---------------
    bFunctionLength          : 0x04 (4 bytes)
    bDescriptorType          : 0x24 (Interface)
    bDescriptorSubType       : 0x02 (Abstract Control Management Functional Descriptor)
    bmCapabilities           : 0x06
     D7..4:                  : 0x00 (Reserved)
     D3   :                  : 0x00 (not supports the notification Network_Connection)
     D2   :                  : 0x01 (supports the request Send_Break)
     D1   :                  : 0x01 (supports the request combination of Set_Line_Coding, Set_Control_Line_State, Get_Line_Coding, and the notification Serial_State)
     D0   :                  : 0x00 (not supports the request combination of Set_Comm_Feature, Clear_Comm_Feature, and Get_Comm_Feature)
    Data (HexDump)           : 04 24 02 06                                       .$..

            -------------- CDC Interface Descriptor ---------------
    bFunctionLength          : 0x05 (5 bytes)
    bDescriptorType          : 0x24 (Interface)
    bDescriptorSubType       : 0x06 (Union Functional Descriptor)
    bControlInterface        : 0x00
    bSubordinateInterface[0] : 0x01
    Data (HexDump)           : 05 24 06 00 01                                    .$...

            ----------------- Endpoint Descriptor -----------------
    bLength                  : 0x07 (7 bytes)
    bDescriptorType          : 0x05 (Endpoint Descriptor)
    bEndpointAddress         : 0x82 (Direction=IN EndpointID=2)
    bmAttributes             : 0x03 (TransferType=Interrupt)
    wMaxPacketSize           : 0x0040 (64 bytes)
    bInterval                : 0x08 (8 ms)
    Data (HexDump)           : 07 05 82 03 40 00 08                              ....@..

            ---------------- Interface Descriptor -----------------
    bLength                  : 0x09 (9 bytes)
    bDescriptorType          : 0x04 (Interface Descriptor)
    bInterfaceNumber         : 0x01
    bAlternateSetting        : 0x00
    bNumEndpoints            : 0x02 (2 Endpoints)
    bInterfaceClass          : 0x0A (CDC-Data)
    bInterfaceSubClass       : 0x00
    bInterfaceProtocol       : 0x00
    iInterface               : 0x00 (No String Descriptor)
    Data (HexDump)           : 09 04 01 00 02 0A 00 00 00                        .........

            ----------------- Endpoint Descriptor -----------------
    bLength                  : 0x07 (7 bytes)
    bDescriptorType          : 0x05 (Endpoint Descriptor)
    bEndpointAddress         : 0x01 (Direction=OUT EndpointID=1)
    bmAttributes             : 0x02 (TransferType=Bulk)
    wMaxPacketSize           : 0x0040 (64 bytes)
    bInterval                : 0x01 (ignored)
    Data (HexDump)           : 07 05 01 02 40 00 01                              ....@..

            ----------------- Endpoint Descriptor -----------------
    bLength                  : 0x07 (7 bytes)
    bDescriptorType          : 0x05 (Endpoint Descriptor)
    bEndpointAddress         : 0x81 (Direction=IN EndpointID=1)
    bmAttributes             : 0x02 (TransferType=Bulk)
    wMaxPacketSize           : 0x0040 (64 bytes)
    bInterval                : 0x01 (ignored)
    Data (HexDump)           : 07 05 81 02 40 00 01                              ....@..

        ----------------- Device Qualifier Descriptor -----------------
    Error                    : ERROR_GEN_FAILURE

          -------------------- String Descriptors -------------------
                 ------ String Descriptor 0 ------
    bLength                  : 0x04 (4 bytes)
    bDescriptorType          : 0x03 (String Descriptor)
    Language ID[0]           : 0x0409 (English - United States)
    Data (HexDump)           : 04 03 09 04                                       ....
                 ------ String Descriptor 1 ------
    bLength                  : 0x14 (20 bytes)
    bDescriptorType          : 0x03 (String Descriptor)
    Language 0x0409          : "Cobolt AB"
    Data (HexDump)           : 14 03 43 00 6F 00 62 00 6F 00 6C 00 74 00 20 00   ..C.o.b.o.l.t. .
                               41 00 42 00                                       A.B.
                 ------ String Descriptor 2 ------
    bLength                  : 0x30 (48 bytes)
    bDescriptorType          : 0x03 (String Descriptor)
    Language 0x0409          : "Cobolt Laser Driver MLD"
    Data (HexDump)           : 30 03 43 00 6F 00 62 00 6F 00 6C 00 74 00 20 00   0.C.o.b.o.l.t. .
                               4C 00 61 00 73 00 65 00 72 00 20 00 44 00 72 00   L.a.s.e.r. .D.r.
                               69 00 76 00 65 00 72 00 20 00 4D 00 4C 00 44 00   i.v.e.r. .M.L.D.
                 ------ String Descriptor 3 ------
    bLength                  : 0x1A (26 bytes)
    bDescriptorType          : 0x03 (String Descriptor)
    Language 0x0409          : "000013245678"
    Data (HexDump)           : 1A 03 30 00 30 00 30 00 30 00 31 00 33 00 32 00   ..0.0.0.0.1.3.2.
                               34 00 35 00 36 00 37 00 38 00                     4.5.6.7.8.
                 ----- String Descriptor 0xEE -----
    bLength                  : 0x02 (2 bytes)
    bDescriptorType          : 0x03 (String Descriptor)
    Language 0x0409          : ""  *!*CAUTION  zero length
    Data (HexDump)           : 02 03     
    """