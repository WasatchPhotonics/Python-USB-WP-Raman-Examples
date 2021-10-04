#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

#import common

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000

VR_READ_CCD_TEMP = 0xd7

buf = [0] * 2

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)

if not dev:
    print("No spectrometers found")
    sys.exit()

result = dev.ctrl_transfer(DEVICE_TO_HOST, VR_READ_CCD_TEMP, 0, 0, buf, TIMEOUT_MS)
print("CCD Temp Value: 0x%04x" % (result[1] << 8 | result[0]))