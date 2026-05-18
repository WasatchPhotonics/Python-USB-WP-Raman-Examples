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
SC_SET_BATT_LASER_SHUT_OFF_TH_DEG_C = 0xb0

parser = argparse.ArgumentParser()
parser.add_argument("--temp", type=int, help="temp threshold range is 0 to 127 deg C, -1 to disable")
args = parser.parse_args()

thVal = -1

if args.temp is None:
   print("temp threshold range is 0 to 127 deg C, -1 to disable")
   quit()

if args.temp is not None:
   thVal = args.temp
   print("setting battery temperature threshold to {} deg C ".format(thVal))
   if thVal < -1 or thVal > 127:
      print("temp threshold range is 0 to 127 deg C, -1 to disable")
      quit()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def set_batt_laser_shut_off_th_val(thVal):
    send_cmd(0xff, SC_SET_BATT_LASER_SHUT_OFF_TH_DEG_C, thVal)
       
set_batt_laser_shut_off_th_val(thVal)
