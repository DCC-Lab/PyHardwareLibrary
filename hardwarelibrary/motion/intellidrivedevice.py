from hardwarelibrary.physicaldevice import *
from hardwarelibrary.motion.rotationmotiondevice import *
from hardwarelibrary.communication.communicationport import *
from hardwarelibrary.communication.usbport import USBPort
from hardwarelibrary.communication.serialport import SerialPort
from hardwarelibrary.communication.commands import DataCommand
from hardwarelibrary.communication.debugport import DebugPort

import re
import time
from struct import *

from pyftdi.ftdi import Ftdi #FIXME: should not be here.

class State(Enum):
    notInit = 0,
    init = 1,
    unknown = 2,
    referenced = 3,
    configuration = 4,
    homing = 5,
    moving = 6,
    ready = 7,
    disable = 8,
    jogging = 9


class IntellidriveDevice(RotationDevice):
    classIdVendor = 4930
    classIdProduct = 1

    def __init__(self):
        super().__init__(serialNumber=serialNumber, idVendor=self.classIdVendor, idProduct=self.classIdProduct)
        self.orientation = None
        self.internalState = State.notInit
        self.stepsPerDegree = 138.888;

    def doGetOrientation(self) -> float:
        return self._debugOrientation

    def doMoveTo(self, angle):
        self._debugOrientation = angle

    def doMoveBy(self, displacement):
        self._debugOrientation += angle

    def doHome(self):
        self._debugOrientation = 0

    def doInitializeDevice(self): 
        try:
            if self.serialNumber == "debug":
                self.port = self.DebugSerialPort()
            else:
                portPath = SerialPort.matchAnyPort(idVendor=self.idVendor, idProduct=self.idProduct, serialNumber=self.serialNumber)
                if portPath is None:
                    raise PhysicalDevice.UnableToInitialize("No Intellidrive Device connected")

                self.port = SerialPort(portPath=portPath)
                self.port.open(baudRate=9600, bits=8, parity = None, stop=1, timeout=10)

            if self.port is None:
                raise PhysicalDevice.UnableToInitialize("Cannot allocate port {0}".format(portPath))

            self.serialPort.writeString("s r0x24 31\r", expectStringMatching:"ok\r")
            self.serialPort.writeString("s r0xc2 514\r", expectStringMatching:"ok\r")

            self,internalState = State.ready

        except Exception as error:
            if self.port is not None:
                if self.port.isOpen:
                    self.port.close()
            self.internalState = State.notInit
            raise PhysicalDevice.UnableToInitialize(error)

    def doShutdownDevice(self):
        self.port.close()
        self.port = None

    def doGetOrientation(self) -> float:
        raise NotImplementedError()

    def doMoveTo(self, angle):
        raise NotImplementedError()

    def doMoveBy(self, displacement):
        raise NotImplementedError()

    def doHome(self):
        raise NotImplementedError()
     

"""
Objective-C code that works:
//
//  IntellidriveDevice.m
//  HardwareLibrary
//
//  Created by Daniel Côté on 2016-05-06.
//  Copyright © 2016 Daniel Côté. All rights reserved.
//

//#import <HardwareLibrary/IntellidriveDevice.h>

#define WORKAROUND_ABSENT_ENCODER 1

enum {
    kStateNotInit = 0,
    kStateInit = 1,
    kStateUnknown = 2,
    kStateNotReferenced = 3,
    kStateConfiguration = 4,
    kStateHoming = 5,
    kStateMoving = 6,
    kStateReady = 7,
    kStateDisable = 8,
    kStateJogging = 9
};

@interface IntellidriveDevice ()

@property (weak, readonly) NSString* bsdPath;
@property (assign) int internalState;
//@property (strong) NSOperationQueue* queue;
@property (assign) double stepsPerDegree;
#ifdef WORKAROUND_ABSENT_ENCODER
@property (assign) NSInteger steps;
#endif

@end

@implementation IntellidriveDevice

- (instancetype) initWithSerialNumber:(NSString *)serialNumber
{
    return [ self initWithVendorId:@(INTELLIDRIVE_VENDORID) productId:@(INTELLIDRIVE_PRODUCTID) serialNumber:serialNumber];
}

- (id) initWithVendorId:(NSNumber *)vendorID productId:(NSNumber *)productID serialNumber:(NSString *)serialNumber
{
    if (INTELLIDRIVE_VENDORID == 0xffff || INTELLIDRIVE_PRODUCTID == 0xffff) {
        @throw [ NSException exceptionWithName:@"Fix vendorID" reason:@"" userInfo:nil];
    }
    
    if ( [ vendorID unsignedIntegerValue] == INTELLIDRIVE_VENDORID && [ productID unsignedIntegerValue] == INTELLIDRIVE_PRODUCTID) {
        if ( ( self = [ super initWithVendorId:vendorID productId:productID serialNumber:serialNumber ] ) != nil ) {
            self.internalState = kStateNotInit;
            self.stepsPerDegree = 138.888;
        }
    } else {
        self = nil;
    }

    
    return self;
}

- (void)doReadFromDevice
{
    [self doGetTheta];
    [self doReadState];
}

- (void)doWriteToDevice
{
    [self doMoveToTheta];
}

- (NSError*) doResetDevice
{
    NSError* error = [ self.serialPort writeString:@"r\r"];
    sleep(3);
    return error;
}


- (NSError*) doInitializeDevice
{
    NSError* error = nil;

    if ( [ self.serialNumber matchesRegex:@"debug"]) {
        self.serialPort = [[DebugSerialPortIntellidrive alloc] init];
    } else {
        self.serialPort = [[ SerialPortController sharedController] serialPortWithSerialNumber:self.serialNumber vendorId:self.vendorId productId:self.productId ];
        if ( self.serialPort == nil ) {
            return [NSError HWLErrorUSBDeviceNotFound:self.serialNumber vendorId:self.vendorId productId:self.productId];
        }
    }
    Termios* termios = [[ Termios alloc] initWithBauds:B9600 bits:8 parity:none stop:1];
    [self.serialPort setTermiosOptions:termios];
    self.serialPort.terminator = '\r';
    self.serialPort.distributedLocking = NO;

    @synchronized(self) {
        @try {
            ThrowIfNSError([self.serialPort open]);
            ThrowIfNSError([self.serialPort writeString:@"s r0x24 31\r" expectStringMatching:@"ok\r"]);
            ThrowIfNSError([self.serialPort writeString:@"s r0xc2 514\r" expectStringMatching:@"ok\r"]);
//            ThrowIfNSError([self.serialPort writeString:@"t 2\r" expectStringMatching:@"ok\r"]);
            
            NSDate* start = [ NSDate date];
            while (-[start timeIntervalSinceNow] < 5) {
                @autoreleasepool {
                    ThrowIfNSError([self.serialPort writeString:@"g r0xc9\r"]);
                    NSString* theString;
                    ThrowIfNSError([self.serialPort readString:&theString]);
                    NSString* theValue;
                    [ theString matchRegex:@"v\\s(-?\\d+)" firstCaptureGroup:&theValue];
                    unsigned int parameter = [ theValue intValue];
                    if ( (parameter & 1<<12) != 0)
                        break;
                    usleep(10);
                }
            }

            self.internalState = kStateReady;
            self.steps = 0;
        } @catch (NSError* err) {
            [self.serialPort close];
            error = err;
            self.internalState = kStateNotInit;
        }
    }

    return error;
}

- (NSError*) doShutdownDevice
{
    return [ self.serialPort close];
}

- (void) doMoveToTheta
{
    @synchronized(self) {
        NSError* error;
        ThrowIfNSError([self.serialPort writeString:@"s r0xc8 0\r" expectStringMatching:@"ok\r"]);
        ThrowIfNSError([self.serialPort writeString:@"s r0x24 31\r" expectStringMatching:@"ok\r"]);
        double finalTheta = self.theta;
        int steps = finalTheta * self.stepsPerDegree;
        NSString* commandString = [ NSString stringWithFormat:@"s r0xca %d\r", steps];
        ThrowIfNSError([self.serialPort writeString:commandString expectStringMatching:@"ok\r"]);
        ThrowIfNSError([self.serialPort writeString:@"t 1\r" expectStringMatching:@"ok\r"]);
    #ifdef WORKAROUND_ABSENT_ENCODER
        self.steps = steps;
    #endif
        
        NSDate* start = [ NSDate date];
        
        float thenTheta = NAN;
        while ( -[ start timeIntervalSinceNow] < 2 ) {
            [ self doGetTheta];
            if ( self.theta != thenTheta ) {
                start = [ NSDate date];
                thenTheta = self.theta;
            }
            [ self doReadState ];
            if ( self.internalState == kStateReady)
                break;
            usleep(1000);
        }
        
        if ( error == nil ) {
            [ self doGetTheta];

            if ( error == nil && fabs(self.theta - finalTheta) > 0.1 ) {
                error = [ NSError errorWithDomain:rotationDeviceErrorDomain code:kSMC100UnexpectedPosition userInfo:nil];
            }
        }
    }
}

- (void) doCancelMove
{
    @synchronized(self) {
        NSError* error = [self.serialPort writeString:@"t 0\r" expectStringMatching:@"ok\r"];
#pragma unused(error)
    }
}

- (void) doGetTheta
{
    @synchronized(self) {
    #ifdef WORKAROUND_ABSENT_ENCODER
        self.theta = self.steps / self.stepsPerDegree;
    #else
        NSString* theResponse;
        NSError* error = [self.serialPort writeString:@"g r0x32\r" expectStringMatching:@"v\\s(\\d+)\r" firstCaptureGroupString:&theResponse];
        
        if( error == nil ) {
            self.theta = [ theResponse floatValue ]/self.stepsPerDegree;
            NSDictionary* notificationUserInfo = @{@"theta": @(self.theta)};
            NSNotification* notification = [ NSNotification notificationWithName:DevicePositionNotification object: self userInfo:notificationUserInfo];
            [[ NSNotificationCenter defaultCenter] postNotification:notification];
        }
    #endif
    }
}

-(void) doReadState
{
    @synchronized(self) {
        [self.serialPort writeString:@"g r0xa0\r"];
        NSString* theString;
        [self.serialPort readString:&theString];
        
        NSString* theValue;
        [ theString matchRegex:@"v\\s(\\d+)" firstCaptureGroup:&theValue];
        
        unsigned int parameter = [theValue intValue];
        
        if ( (parameter & 1<<27) != 0)
            self.internalState = kStateMoving;
        else
            self.internalState = kStateReady;
    }
}


@end


"""