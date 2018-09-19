#!/usr/bin/env python -u

################################################################################
# This worked:
#
# $ ./ExtTrigger.py --trigger-source HW --continuous-acquisition --frames-per-trigger 3 --reset 
# uC Revision:       10.0.0.3
# FPGA Revision:     008-007
################################################################################

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
TIMEOUT_MS     = 10000
PIXELS         = 1024

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

def reset():
    print "Integration Time: ", Test_Set(0xb2, 0xbf, args.integration_time_ms, 6) 

    # configure trigger source
    if PID != 0x4000: # not needed on ARM, per https://github.com/WasatchPhotonics/WasatchUSB/issues/2

        print "Continuous Acq:   ", Test_Set(0xc8, 0xcc, (1 if args.continuous_acquisition else 0), 1) 
        print "Continuous Frames:", Test_Set(0xc9, 0xcd, args.frames_per_trigger, 1) 

        if args.trigger_source == "SW":
            print "Trigger Source:   ", Test_Set(0xd2, 0xd3, 0, 1)
        elif args.trigger_source == "HW":
            print "Trigger Source:   ", Test_Set(0xd2, 0xd3, 1, 1) 


################################################################################
# main()
################################################################################

# support SW triggering just so we can confirm the script is otherwise working
parser = argparse.ArgumentParser()
parser.add_argument("--integration-time-ms",    type=int, default=100,    help="integration time (ms)")
parser.add_argument("--trigger-source",         type=str, default='NONE', help="specify trigger source", choices=['NONE', 'SW', 'HW'])
parser.add_argument("--frames-per-trigger",     type=int, default=1,      help="how many frames to collect per trigger")
parser.add_argument("--max-errors",             type=int, default=3,      help="number of permitted USB read errors")
parser.add_argument("--continuous-acquisition", action='store_true',      help="whether to collect multiple spectra per trigger")
parser.add_argument("--reset",                  action='store_true',      help="forcibly reset continuous acquisition after each trigger")
args = parser.parse_args()

# claim USB device
dev = usb.core.find(idVendor=VID, idProduct=PID)
if not dev:
    print "No {0} spectrometers found." % PID
    sys.exit(0)

# initialize test
print "uC Revision:      ", getFirmwareRev()
print "FPGA Revision:    ", getFPGARev()
reset()

print "\nstart sending incoming trigger signals..."
sleep(5)

# loop over acquisitions
frame_count = 0
error_count = 0
while True:
    print "expecting next trigger"

    if args.trigger_source == "SW":
        print "sending SW trigger"
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, ZZ, TIMEOUT_MS)
        
    for i in range(args.frames_per_trigger):
        print "Waiting for data...(20 second timeout)"

        # this try-catch block doesn't help anything
        try:
            data = dev.read(0x82, 2 * PIXELS, 20000) # 20sec timeout
        except Exception as exc:
            if error_count < args.max_errors:
                print "  (ignoring USB error)"
                error_count += 1
            else:
                raise exc

        print("Read frame %d" % frame_count)
        frame_count += 1

    # this reset doesn't seem to help anything
    if args.reset:
        print "Continuous Acq:   ", Test_Set(0xc8, 0xcc, 0, 1) # disable
        sleep(1)
        reset() # re-enable, if configured
        sleep(1)
