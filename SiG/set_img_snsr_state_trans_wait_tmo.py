#!/usr/bin/env python

import sys
import usb.core
import argparse

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000
VR_SET_LASER_WARNING_DELAY = 0x8a

parser = argparse.ArgumentParser()
parser.add_argument("--time", type=int, help="image sensor state transition wait tmo in millisecs (max 65535)")
args = parser.parse_args()

timeMillis= -1

if args.time is None:
   print("specify image sensor state transition wait tmo in millisecs (max 65535 ms) !!")
   quit()
else:
   timeMillis = args.time
   print("tmo", timeMillis)
   if timeMillis < 0 or timeMillis > 65535:
      print("specify image sensor state transition wait tmo in millisecs (max 65535 ms) !!")
      quit()


cmd = VR_SET_LASER_WARNING_DELAY
length = 0
dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0x71, timeMillis, length, TIMEOUT_MS)


