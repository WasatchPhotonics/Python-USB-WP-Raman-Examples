#!/usr/bin/env python

import sys
import usb.core

SC_GET_TEC_WATCHDOG_TMO_REQ = 0x7e

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

data = Get_Value(0xff, SC_GET_TEC_WATCHDOG_TMO_REQ, 2)
# print("data :", data)
val = data[1]
val = val << 8
val += data[0]

print("TEC watchdog timeout is {} secs".format(val))
