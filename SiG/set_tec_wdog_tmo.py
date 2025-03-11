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
SC_SET_TEC_WATCHDOG_TMO_REQ = 0x7d

parser = argparse.ArgumentParser()
parser.add_argument("--time", type=int, help="TEC watchdog timeout in seconds (1 to 65535, 0 to disable)")
args = parser.parse_args()

timeSecs = -1

if args.time is None:
   print("specify TEC watchdog timeout in seconds (1 - 65535, 0 to disable) !!")
   quit()
else:
   timeSecs = args.time
   print("tmo", timeSecs)
   if timeSecs < 0 or timeSecs > 65535:
      print("specify timeout in seconds (1 - 65535, 0 to disable) !!")
      quit()


def set_tec_watchdog_tmo(time):
    cmd = 0xff
    subCmd = SC_SET_TEC_WATCHDOG_TMO_REQ
    value = time
    index = 0
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, SC_SET_TEC_WATCHDOG_TMO_REQ, time, 0, TIMEOUT_MS)

set_tec_watchdog_tmo(timeSecs)
