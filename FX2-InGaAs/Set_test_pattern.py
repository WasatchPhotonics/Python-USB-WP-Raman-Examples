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

dev.ctrl_transfer(HOST_TO_DEVICE, 0xba, 1, 0, Z, TIMEOUT_MS)
print("Enabled test pattern.")
