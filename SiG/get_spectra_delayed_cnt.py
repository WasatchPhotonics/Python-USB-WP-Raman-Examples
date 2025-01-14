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
    # print(f"<< {data}")
    value = 0
    for i in range(lsb_len):
        value |= (data[i] << i)
    # print(f"returning 0x{value:04x} ({value})")
    return value


def get_cnt():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x67, 0, 4, TIMEOUT_MS)
    value = 0
    for i in range(4):
        value |= (data[i] << i)
    return value
    

cnt = get_cnt()
print(cnt)
