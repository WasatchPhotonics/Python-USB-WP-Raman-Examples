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
VR_GET_INTEGRATION_TIME	= 0xbf

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def get_integ_time():
    data = Get_Value(VR_GET_INTEGRATION_TIME, 0x0, 6)
    print("data :", data)
    val = data[2]
    val <<= 8
    val += data[1]
    val <<= 8
    val += data[0]
    return val      

integTimeMS = get_integ_time()
print("integration time is {} ms".format(integTimeMS))
