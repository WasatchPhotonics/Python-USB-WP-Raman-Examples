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
parser.add_argument("--time", type=int, help="LASER warn delay time in seconds (0 to 255)")
args = parser.parse_args()

timeSecs = -1

if args.time is None:
   print("specify LASER warn delay time in seconds (0 - 255) !!")
   quit()
else:
   timeSecs = args.time
   print("tmo", timeSecs)
   if timeSecs < 0 or timeSecs > 255:
      print("specify idle timeout in seconds (0 - 255) !!")
      quit()


def set_laser_warn_delay(time):
    cmd = VR_SET_LASER_WARNING_DELAY
    value = time
    index = 0
    length = 1
    resp = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
    print("resp is ", resp)
    if resp[0] == 0:
       print("laser warn delay set to {} secs".format(time))
    else:
       print("failed to set laser warn delay - error code {}".format(resp[0]))


set_laser_warn_delay(timeSecs)
