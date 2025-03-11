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

def get_img_snsr_state():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0x97, 0, 0, 1, TIMEOUT_MS)
    print(data[0])
    return 


get_img_snsr_state()
