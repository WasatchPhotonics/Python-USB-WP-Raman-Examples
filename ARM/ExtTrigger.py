#!/usr/bin/env python -u

################################################################################
# This script worked with no arguments on the S-00247 ARM unit.
#
# uC Revision:       10.0.0.3
# FPGA Revision:     008-007
#
# A Koolertron DDS Signal Generator was used to generate a 0-3.3V square wave
# at 0.2Hz. The trigger was hooked to pin 10 of J8 on the USB board (GND pin 9).
#
# The USB command sequence is provided in ENG-0073.  Since we were on an ARM, 
# there was no need to set the external trigger source, nor were continuous
# acquisition or frames-per-trigger specified.
################################################################################

import sys
import usb.core
import argparse
import datetime
from time import sleep

################################################################################
# Constants
################################################################################

VID            = 0x24aa
PID            = 0x4000
HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xc0
ZZ             = [0] * 8
PIXELS         = 1024

################################################################################
# Functions
################################################################################

def Get_Value(Command, ByteCount, raw=False):
    RetArray = dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, args.timeout_ms)
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
    result = dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, lsb, msb, ZZ, args.timeout_ms)
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

def display(msg):
    print("%s: %s" % (datetime.datetime.now(), msg))

################################################################################
# main()
################################################################################

# parse cmd-liner args
parser = argparse.ArgumentParser()
parser.add_argument ("--integration-time-ms", type=int, default=100,    help="integration time (ms)")
parser.add_argument ("--timeout-sec",         type=int, default=20,     help="USB timeout (sec)")
args = parser.parse_args()
args.timeout_ms = args.timeout_sec * 1000

# claim USB device
dev = usb.core.find(idVendor=VID, idProduct=PID)
if not dev:
    print("No {0} spectrometers found." % PID)
    sys.exit(0)

# initialize test
print("uC Revision:      ", getFirmwareRev())
print("FPGA Revision:    ", getFPGARev())
print("Integration Time: ", Test_Set(0xb2, 0xbf, args.integration_time_ms, 6)) 

# loop over trigger signals
print("\nstart sending incoming trigger signals...\n")

frames = 0
while True:
    data = dev.read(0x82, 2 * PIXELS, args.timeout_ms) 
    display("  read frame %d" % frames)
    frames += 1
