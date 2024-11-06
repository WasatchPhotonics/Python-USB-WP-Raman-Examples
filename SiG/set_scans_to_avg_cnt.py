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
VR_SET_AVG_SCAN_CNT = 0x62

parser = argparse.ArgumentParser()
parser.add_argument("--cnt", type=int, help="range is 1 to 65535")
args = parser.parse_args()

cnt = -1

if args.cnt is None:
   print("range is 1 to 65535 !!")
   quit()

if args.cnt is not None:
   scan_cnt = args.cnt
   if scan_cnt < 1 or scan_cnt > 65535:
      print("range is 1 to 65535 !!")
      quit()

def send_code(bRequest, wValue=0, wIndex=0, data_or_wLength=None, label=""):
    prefix = "" if not label else ("%s: " % label)
    result = None
    data_or_wLength = [0] * 8

    try:
        result = dev.ctrl_transfer(HOST_TO_DEVICE,
                                   bRequest,
                                   wValue,
                                   wIndex,
                                   data_or_wLength)
    except Exception as exc:
         print("Hardware Failure FID Send Code Problem with ctrl transfer")
         return None

    print("%ssend_code: request 0x%02x value 0x%04x index 0x%04x data/len %s: result 0x%02x" % (
          prefix, bRequest, wValue, wIndex, data_or_wLength, result))
    return result


def send_cmd(cmd, value, index=0, buf=None):
    print("send_cmd: request 0x%02x value 0x%04x index 0x%04x" % (
          cmd, value, index))
    result = dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)
    print("send_cmd: request 0x%02x value 0x%04x index 0x%04x : result %s" % (
          cmd, value, index, result))


def set_avg_scan_cnt(scan_cnt): 
    cmd = VR_SET_AVG_SCAN_CNT
    send_code(0xff, cmd, scan_cnt)
       

set_avg_scan_cnt(scan_cnt)
