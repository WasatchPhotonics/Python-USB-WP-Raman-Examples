#!/usr/bin/env python

import sys
import usb.core

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000
VR_GET_CCD_OFFSET = 0xc4

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def get_ccd_offset():
    data = Get_Value(VR_GET_CCD_OFFSET, 0x0, 2)
    print("data :", data)
    val = data[1]
    val <<= 8
    val += data[0]
    if val & 0x8000:
       val = val - 65536 
    return val      

offset = get_ccd_offset()
print("ccd offset is {}".format(offset))
