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

print(dev.ctrl_transfer(DEVICE_TO_HOST, 0xec, 0, 0, Z, TIMEOUT_MS))
print("Set gain to 2")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xeb, 0, 0, Z, TIMEOUT_MS)
print(dev.ctrl_transfer(DEVICE_TO_HOST, 0xec, 0, 0, Z, TIMEOUT_MS))
