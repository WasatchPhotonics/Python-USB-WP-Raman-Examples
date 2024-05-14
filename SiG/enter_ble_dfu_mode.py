#!/usr/bin/env python

import sys
import usb.core

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

try:
  result = dev.ctrl_transfer(HOST_TO_DEVICE,
                             0xff,
                             0x36,
                             0,
                             64)
except Exception as exc:
  print("Failed to Send Code Problem with ctrl transfer")

