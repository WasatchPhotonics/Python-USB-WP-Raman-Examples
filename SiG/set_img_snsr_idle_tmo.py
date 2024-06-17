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
VR_SET_IMAGE_SNSR_IDLE_TIMEOUT = 0x8e

parser = argparse.ArgumentParser()
parser.add_argument("--time", type=int, help="Image sensor idle timeout in seconds (0 to 65535)")
args = parser.parse_args()

tmoVal = -1

if args.time is None:
   print("specify idle timeout in seconds (0 - 65535) !!")
   quit()

if args.time is not None:
   tmoVal = args.time
   # print("tmo val", attnSetPoint)
   if tmoVal < 0 or tmoVal > 65535:
      print("specify idle timeout in seconds (0 - 65535) !!")
      quit()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

def set_img_snsr_idle_tmo(tmo):
    cmd = VR_SET_IMAGE_SNSR_IDLE_TIMEOUT
    send_cmd(cmd, tmo)
       

set_img_snsr_idle_tmo(tmoVal)
