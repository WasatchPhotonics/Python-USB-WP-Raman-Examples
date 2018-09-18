#!/usr/bin/env python -u
################################################################################
#                                BatchTest.py                                  #
################################################################################
#                                                                              #
#  DESCRIPTION:  An extended version of SetTest.py which runs a set of simple  #
#                commands repeatedly against the spectrometer to generate      #
#                conditions of high traffic, for purposes of characterizing    #
#                communication issues under high load.                         #
#                                                                              #
################################################################################

import sys
import usb.core
import datetime
from time import sleep

# select product
HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
ZZ = [0] * BUFFER_SIZE
TIMEOUT = 1000
VID = 0x24aa
PID = 0x1000  # 0x1000 = Silicon FX2, 0x2000 = InGaAs FX2, 0x4000 = ARM

def Get_Value(Command, ByteCount):
    throttle_usb()
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

    throttle_usb()
    Ret = dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT)
    if BUFFER_SIZE != Ret:
        return ('Set {0:x}  Fail'.format(SetCommand))
    else:
        RetValue = Get_Value(GetCommand, RetLen)
        if RetValue is not None and SetValue == RetValue:
            return ('Get 0x%04x Success: Txd:0x%04x == Rxd:0x%04x' % (GetCommand, SetValue, RetValue))    
        else:
            Test_Set.errors += 1
            return ('Get 0x%04x Failure: Txd:0x%04x != Rxd: %s' % (GetCommand, SetValue, RetValue))    
Test_Set.errors = 0

def Get_FPGA_Revision():
    throttle_usb()
    buf = dev.ctrl_transfer(DEVICE_TO_HOST, 0xb4, 0, 0, 7, TIMEOUT)
    s = ""
    for c in buf:
        s += chr(c)
    return s

def throttle_usb():
    if throttle_usb.delay_ms > 0:
        if throttle_usb.last_usb_timestamp is not None:
            next_usb_timestamp = throttle_usb.last_usb_timestamp + datetime.timedelta(milliseconds=throttle_usb.delay_ms)
            if datetime.datetime.now() < next_usb_timestamp:
                while datetime.datetime.now() < next_usb_timestamp:
                    sleep(0.001) 
        throttle_usb.last_usb_timestamp = datetime.datetime.now()
    throttle_usb.count += 1
throttle_usb.last_usb_timestamp = None
throttle_usb.delay_ms = 0
throttle_usb.count = 0

# MZ: possibly relevant: https://bitbucket.org/benallard/galileo/issues/251/usbcoreusberror-errno-5-input-output-error
# def attempt_recovery():
#     global dev
# 
#     print "resetting device"
#     dev.reset()
#     sleep(2)
# 
#     if True:
#         dev = None
#         sleep(2)
#         
#         print "re-enumerating USB"
#         dev = usb.core.find(idVendor=VID, idProduct=PID)
#         sleep(2)
# 
#         if dev is None:
#             print "Failed to re-enumerate device"
#             sys.exit()
# 
# def reset_fpga():
#     print "resetting FPGA"
#     buf = [0] * 8
#     dev.ctrl_transfer(HOST_TO_DEVICE, 0xb5, 0, 0, buf, TIMEOUT)
#     sleep(2)

################################################################################
# main()
################################################################################

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print "No spectrometers found."
    sys.exit()

print dev

fpga_rev = Get_FPGA_Revision()
print 'FPGA Ver %s' % fpga_rev
print 'Testing Set Commands'
print "\nPress Ctrl-C to exit..."

iterations = 0
while True:
    try:
        print "Iteration %d: (%d errors)" % (iterations, Test_Set.errors)
        print "  Integration Time ", Test_Set(0xb2, 0xbf, 100, 6)
        print "  CCD Offset       ", Test_Set(0xb6, 0xc4,   0, 2)
        print "  CCD Gain         ", Test_Set(0xb7, 0xc5, 487, 2)
        print "  CCD TEC Enable   ", Test_Set(0xd6, 0xda,   1, 1)
        print "  CCD TEC Disable  ", Test_Set(0xd6, 0xda,   0, 1)
        iterations += 1
    except Exception as ex:
        print "Caught exception after %d USB calls" % throttle_usb.count 
        print ex
        sys.exit()
