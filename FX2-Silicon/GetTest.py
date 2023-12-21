#!/usr/bin/env python -u

import sys
import usb.core
import datetime
from time import sleep

dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def Get_Raw(Command, ByteCount=64, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, TIMEOUT_MS)

def Get_Value(Command, ByteCount, index=0):
    try:
        RetVal = 0
        RetArray = Get_Raw(Command, ByteCount, index)
        for i in range (0, ByteCount):
            RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
        return (RetVal, RetArray)
    except:
        return ("error", "error")

print("Integration Time   %8s %s" % Get_Value(0xbf, 6))
print("CCD Offset         %8s %s" % Get_Value(0xc4, 2))
print("CCD Gain           %8s %s" % Get_Value(0xc5, 2))
print("CCD Temp SP        %8s %s" % Get_Value(0xd9, 2))
print("CCD Temp ENABLE    %8s %s" % Get_Value(0xda, 1))
print("Laser Mod Duration %8s %s" % Get_Value(0xc3, 5))
print("Laser Mod Delay    %8s %s" % Get_Value(0xca, 5))
print("Laser Mod Period   %8s %s" % Get_Value(0xcb, 5))
print("Laser Diode Temp   %8s %s" % Get_Value(0xd5, 2))
print("Actual Int Time    %8s %s" % Get_Value(0xdf, 6))
print("CCD Temperature    %8s %s" % Get_Value(0xd7, 2))
print("Interlock          %8s %s" % Get_Value(0xef, 1))
print("uC FW Version      %s"     % ".".join(str(x) for x in list(reversed(list(Get_Raw(0xc0))))))
print("FPGA FW Version    %s"     % "".join(chr(c) for c in Get_Raw(0xb4)))
