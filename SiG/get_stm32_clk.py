#!/usr/bin/env python

import sys
import usb.core
from datetime import datetime

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def get_uint(bRequest, wValue, wIndex=0, lsb_len=4):
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
    value = 0
    # print(data)
    for i in range(lsb_len):
        value <<= 8
        value |= data[lsb_len -1 - i]
    return value

report = { "STM32 SYSCLK" : get_uint(0xff, 0x70), }

for label, value in report.items():
    value = value/1000000
    print("%-20s: %s MHZ" % (label, value))

print()
