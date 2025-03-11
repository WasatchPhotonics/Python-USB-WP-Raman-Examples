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

data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x7a, 0, 20, TIMEOUT_MS)

print(data)

cnt = data[3]
cnt = (cnt << 8) | data[2]
cnt = (cnt << 8) | data[1]
cnt = (cnt << 8) | data[0]

print("")
print("Total Int Cnt:", cnt)
    
cnt = data[3 + 4]
cnt = (cnt << 8) | data[2 + 4]
cnt = (cnt << 8) | data[1 + 4]
cnt = (cnt << 8) | data[0 + 4]

print("Level 0 Cnt:", cnt)

cnt = data[3 + 8]
cnt = (cnt << 8) | data[2 + 8]
cnt = (cnt << 8) | data[1 + 8]
cnt = (cnt << 8) | data[0 + 8]

print("Level 1 Cnt:", cnt)


cnt = data[3 + 12]
cnt = (cnt << 8) | data[2 + 12]
cnt = (cnt << 8) | data[1 + 12]
cnt = (cnt << 8) | data[0 + 12]

print("0-to-1 TS:", cnt)

cnt = data[3 + 16]
cnt = (cnt << 8) | data[2 + 16]
cnt = (cnt << 8) | data[1 + 16]
cnt = (cnt << 8) | data[0 + 16]

print("1-to-0 TS:", cnt)

