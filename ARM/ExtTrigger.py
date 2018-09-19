#!/usr/bin/env python -u

import sys
import usb.core
import argparse
from time import sleep

################################################################################
# Constants
################################################################################

VID            = 0x24aa
PID            = 0x4000
HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
ZZ             = [0] * 8
TIMEOUT_MS     = 1000
PIXELS         = 1024
INTEG_TIME_MS  = 10

################################################################################
# Functions
################################################################################

def Get_Value(Command, ByteCount, raw=False):
    RetArray = dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, TIMEOUT_MS)
    if raw:
        RetVal = RetArray
    else:
        RetVal = 0
        for i in range(len(RetArray)):
            RetVal = (RetVal << 8) | RetArray[ByteCount - i - 1]
    return RetVal

def Test_Set(SetCommand, GetCommand, SetValue, RetLen):
    lsb   =  SetValue        & 0xffff
    msb   = (SetValue >> 16) & 0xffff
    ZZ[0] = (SetValue >> 32) & 0xff
    result = dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, lsb, msb, ZZ, TIMEOUT_MS)
    if result != len(ZZ):
        return 'Set %02x failed' % SetCommand
    else:
        RetValue = Get_Value(GetCommand, RetLen)
        if SetValue == RetValue:
            return 'Get %02x Success. Txd:0x%05x Rxd:0x%05x' % (GetCommand, SetValue, RetValue)
        else:
            return 'Get %02x Failure. Txd:0x%05x Rxd:0x%05x' % (GetCommand, SetValue, RetValue)

def getFirmwareRev():
    return ".".join(reversed([str(int(x)) for x in Get_Value(0xc0, 4, raw=True)]))

def getFPGARev():
    return "".join(chr(x) for x in Get_Value(0xb4, 7, raw=True))

################################################################################
# main()
################################################################################

# support SW triggering just so we can confirm the script is otherwise working
parser = argparse.ArgumentParser()
parser.add_argument("--trigger-source", default="NONE", choices=['NONE', 'SW', 'HW'], help="specify trigger source")
args = parser.parse_args()

# claim USB device
dev = usb.core.find(idVendor=VID, idProduct=PID)
if not dev:
    print "No ARM spectrometers found."
    sys.exit(0)

# initialize test
print "uC Revision:      ", getFirmwareRev()
print "FPGA Revision:    ", getFPGARev()
print "Integration Time: ", Test_Set(0xb2, 0xbf, INTEG_TIME_MS, 6)

# configure trigger source
if args.trigger_source == "SW":
    print "Trigger Source:   ", Test_Set(0xd2, 0xd3, 0, 1)
elif args.trigger_source == "HW":
    print "Trigger Source:   ", Test_Set(0xd2, 0xd3, 1, 1) # not needed on ARM, per https://github.com/WasatchPhotonics/WasatchUSB/issues/2

print "\nstart sending incoming trigger signals..."
sleep(5)

# loop over acquisitions
print "Waiting for data... (20 second timeout, ctrl-C to exit)"
frames = 0
while True:
    if args.trigger_source == "SW":
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, ZZ, TIMEOUT_MS)
        
    data = dev.read(0x82, 2 * PIXELS, 20000) # 20sec timeout
    print("Read frame %d" % frames)

    frames += 1
