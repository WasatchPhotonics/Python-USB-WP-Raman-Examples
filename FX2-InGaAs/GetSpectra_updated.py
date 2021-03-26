#!/usr/bin/env python -u

import sys
import usb.core
import datetime
import time
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

pixels = 512
integration_time_ms = 200

print("Set integraiton time 10ms")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, integration_time_ms & 0xffff, 0, Z, TIMEOUT_MS)

print("Start Data Acquisition")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, Z, TIMEOUT_MS)

# MZ: this works from Windows but not Mac?
data = dev.read(0x82, pixels * 2)

print("Read %d pixels (%d bytes)" % (pixels, len(data)))
last = -1
for i in range(0, len(data), 2):
    intensity = data[i] | (data[i+1] << 8)
    sys.stdout.write("pixel %4d: 0x%04x (%d)" % (i / 2, intensity, intensity, ))
    if last == intensity:
        sys.stdout.write(" (duplicate)")
    sys.stdout.write("\n")
    last = intensity
