#!/usr/bin/env python -u

import sys
import usb.core

dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if dev is None:
    print("No spectrometers found")
    sys.exit(1)

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000
Z = [0] * 8

def Get_Value(Command, ByteCount, raw=False):
    RetArray = dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, TIMEOUT_MS)
    if raw:
        RetVal = RetArray
    else:
        RetVal = 0
        for i in range(len(RetArray)):
            RetVal = (RetVal << 8) | RetArray[ByteCount - i - 1]
    return RetVal

def getFirmwareRev():
    return ".".join(reversed([str(int(x)) for x in Get_Value(0xc0, 4, raw=True)]))

def getFPGARev():
    return "".join(chr(x) for x in Get_Value(0xb4, 7, raw=True))

print("microcontroller firmware: %s" % getFirmwareRev())
print("           FPGA firmware: %s" % getFPGARev())
    
