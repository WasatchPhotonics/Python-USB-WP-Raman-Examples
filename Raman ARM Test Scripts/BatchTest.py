#!/usr/bin/env python

import usb.core
import datetime
from time     import sleep

# select product
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print dev
HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
ZZ = [0] * BUFFER_SIZE
TIMEOUT = 1000

ITERATIONS = 10000
MIN_USB_INTERVAL_MS = 10
last_usb_timestamp = None

def Get_Value(Command, ByteCount):
    wait_for_usb_available()
    RetVal = 0
    RetArray = dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, TIMEOUT)
    if RetArray is None or len(RetArray) < ByteCount:
        return None
    for i in range (0, ByteCount):
        RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
    return RetVal
    
def Test_Set(SetCommand, GetCommand, SetValue, RetLen):
    SetValueHigh = (SetValue >> 16) & 0xffff
    SetValueLow  = SetValue & 0xffff
    FifthByte = (SetValue >> 32) & 0xff
    ZZ[0] = FifthByte

    wait_for_usb_available()
    Ret = dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT)
    if BUFFER_SIZE != Ret:
        return ('Set {0:x}  Fail'.format(SetCommand))
    else:
        RetValue = Get_Value(GetCommand, RetLen)
        if RetValue is not None and SetValue == RetValue:
            return ('Get 0x%04x Success: Txd:0x%04x == Rxd:0x%04x' % (GetCommand, SetValue, RetValue))    
        else:
            return ('Get 0x%04x Failure: Txd:0x%04x != Rxd: %s' % (GetCommand, SetValue, RetValue))    

def Get_FPGA_Revision():
    wait_for_usb_available()
    buf = dev.ctrl_transfer(DEVICE_TO_HOST, 0xb4, 0, 0, 7, TIMEOUT)
    s = ""
    for c in buf:
        s += chr(c)
    return s

def wait_for_usb_available():
    global last_usb_timestamp # why does only THIS variable need 'global'...?
    if MIN_USB_INTERVAL_MS > 0:
        if last_usb_timestamp is not None:
            next_usb_timestamp = last_usb_timestamp + datetime.timedelta(milliseconds=MIN_USB_INTERVAL_MS)
            if datetime.datetime.now() < next_usb_timestamp:
                while datetime.datetime.now() < next_usb_timestamp:
                    sleep(0.001) 
        last_usb_timestamp = datetime.datetime.now()

fpga_rev = Get_FPGA_Revision()
print 'FPGA Ver %s' % fpga_rev
print 'Testing Set Commands'
print "\nPress Ctrl-C to exit..."

for iteration in range(ITERATIONS):
    print "Iteration %d:" % iteration
    print "  Integration Time ", Test_Set(0xb2, 0xbf, 100, 6)
    print "  CCD Offset       ", Test_Set(0xb6, 0xc4,   0, 2)
    print "  CCD Gain         ", Test_Set(0xb7, 0xc5, 487, 2)
    print "  CCD TEC Enable   ", Test_Set(0xd6, 0xda,   1, 1)
    print "  CCD TEC Disable  ", Test_Set(0xd6, 0xda,   0, 1)
