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
VR_SET_SPECTRA_LINE_FRAME_HDR_CFG = 0x98
parser = argparse.ArgumentParser()
parser.add_argument("--opn", type=int, help="On 1, Off 0")
args = parser.parse_args()

opn = -1

if args.opn is None:
   print("On 1, Off 0")
   quit()

if args.opn is not None:
   opn = args.opn
   if opn < 0 or opn > 1:
      print("On 1, Off 0")
      quit()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

cmd = VR_SET_SPECTRA_LINE_FRAME_HDR_CFG
send_cmd(cmd, opn)
       

