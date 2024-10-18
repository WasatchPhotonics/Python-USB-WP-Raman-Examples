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
VR_SET_TEC_MODE = 0x84

parser = argparse.ArgumentParser()
parser.add_argument("--mode", type=int, help="TEC mode (0-3)")
args = parser.parse_args()

mode = -1

if args.mode is None:
   print("specify TEC Mode (0 - 3) !!")
   quit()
else:
   mode = args.mode
   print("mode", mode)
   if mode < 0 or mode > 3:
      print("specify TEC Mode (0 - 3) !!")
      quit()

def set_tec_mode(mode):
    cmd = VR_SET_TEC_MODE
    print("setting mode to ", mode)
    data = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, mode, 0, 1, TIMEOUT_MS)
    print(data)

set_tec_mode(mode)
