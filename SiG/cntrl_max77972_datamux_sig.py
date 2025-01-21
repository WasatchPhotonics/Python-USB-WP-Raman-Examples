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

parser = argparse.ArgumentParser()
parser.add_argument("--b", type=int, help="GPIO value to set (0 or 1)")
args = parser.parse_args()


bitVal = 0x0

if args.b is None:
   print("specify bit value (0 or 1) !!")
   quit()
else:
   bitVal = args.b

buff = [bitVal]
dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0x7b, 0, buff, TIMEOUT_MS)
 
print('done')
