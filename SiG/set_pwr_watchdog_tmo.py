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
SC_GET_POWER_WATCHDOG_SEC = 0x30

parser = argparse.ArgumentParser()
parser.add_argument("--time", type=int, help="power watchdog timeout in seconds (1 to 65535, 0 to disable)")
args = parser.parse_args()

timeSecs = -1

if args.time is None:
   print("specify power watchdog timeout in seconds (1 - 65535, 0 to disable) !!")
   quit()
else:
   timeSecs = args.time
   print("tmo", timeSecs)
   if timeSecs < 0 or timeSecs > 65535:
      print("specify timeout in seconds (1 - 65535, 0 to disable) !!")
      quit()


def set_pwr_watchdog_tmo(time):
    cmd = 0xff
    subCmd = SC_GET_POWER_WATCHDOG_SEC
    value = time
    index = 0
    length = 1
    resp = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, subCmd, value, length, TIMEOUT_MS)
    print("resp is ", resp)
    if resp[0] == 0:
       print("laser warn delay set to {} secs".format(time))
    else:
       print("failed to set laser warn delay - error code {}".format(resp[0]))


set_pwr_watchdog_tmo(timeSecs)
