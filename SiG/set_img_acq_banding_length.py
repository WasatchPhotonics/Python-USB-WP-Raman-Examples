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
VR_SET_ACQ_BANDING_LENGTH_REQ = 0x9a

parser = argparse.ArgumentParser()
parser.add_argument("--blen", type=int, help="Image acquisition banding length ")
args = parser.parse_args()

bLenVal = -1

if args.blen is None:
   print("specify valid image acquisition banding length !!")
   quit()

if args.blen is not None:
   bLenVal = args.blen
   if bLenVal < 0:
      print("specify valid image acquisition banding length !!")
      quit()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

def set_img_acq_banding_length(val):
    cmd = VR_SET_ACQ_BANDING_LENGTH_REQ
    send_cmd(cmd, val)
       

set_img_acq_banding_length(bLenVal)
