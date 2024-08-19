#!/usr/bin/env python

import sys
import usb.core
import argparse
import time
import datetime
from time import sleep

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 20000

SIG_LOG_USB_CMD=0x81


def get_next_log():
    raw = dev.ctrl_transfer(DEVICE_TO_HOST, SIG_LOG_USB_CMD, 0x0, 0, 64, TIMEOUT_MS)
    len = raw[0]
    #print("-----------------------------------------------------------------")
    #print("log len ", len)
    #print(raw)
    if len == 0:
       #print("No fresh log entries ... ")
       print(".")
       sleep(1)
    else:
       logStr=""
       for i in raw[1:]:
           # print(i, chr(i))
           logStr += chr(i)
           if i == 0:
              break
       
       disp = True

       if args.filter is not None:
          disp = False

          if "ble-ka" in args.filter:
              if "BLE-T KA" in logStr or "BLE-R KA" in logStr:
                disp = True

          if "batt" in args.filter:
             if "B_I" in logStr or "B_V" in logStr or "B_S" in logStr or "(UB) SOC" in logStr:
                disp = True
       if disp:
          print(datetime.datetime.now(), logStr)


parser = argparse.ArgumentParser()
parser.add_argument("--filter", type=str, help="filter topics. Example: --filter=batt, ble-ka")
args = parser.parse_args()

if args.filter is not None:
    print("Filter topics {}".format(args.filter))

while (1):
  get_next_log();
