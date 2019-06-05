#!/usr/bin/env python -u

import usb.core
import datetime
import sys
from time import sleep

# Select Product
dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if not dev:
    print("No spectrometer found")
    sys.exit()

# print dev

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000
SECONDARY_COMMAND = 0xff
GET_MODEL_CONFIG = 0x01
PAGE_SIZE = 64

for page in range(5):
    buf = dev.ctrl_transfer(DEVICE_TO_HOST, 
                            SECONDARY_COMMAND, 
                            GET_MODEL_CONFIG, 
                            page, 
                            PAGE_SIZE, 
                            TIMEOUT_MS)
    print("\nEEPROM page %d:" % page)
    for i in range(len(buf)):
        sys.stdout.write("%02x " % buf[i])
        if (i + 1) % 16 == 0:
            sys.stdout.write("\n")
