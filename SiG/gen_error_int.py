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
parser.add_argument("--num", type=int, help="0 - 31")
args = parser.parse_args()

errorIntNr = -1

if args.num is None:
   print("specify error int number (0 - 31) !!")
   quit()
else:
   errorIntNr = args.num
   print("error int nr requested", errorIntNr)
   if errorIntNr < 0 or errorIntNr > 31:
      print("specify error int number (0 - 31) !!")
      quit()

def set_tec_mode(errorIntNr):
    print("generating error int nr", errorIntNr)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0xc0, errorIntNr, 0, TIMEOUT_MS)

set_tec_mode(errorIntNr)
