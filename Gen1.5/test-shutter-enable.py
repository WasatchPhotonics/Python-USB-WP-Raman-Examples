#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

import common

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if not dev:
    print("No spectrometers found")
    sys.exit()

SET_CMD = 0x30
GET_CMD = 0x31
SLEEP_SEC = 3

print("Enabling shutter for %d sec..." % SLEEP_SEC)
common.send_cmd(dev, SET_CMD, 1)
common.verify_state(dev, GET_CMD, msb_len=1, expected=1, label="shutter")

print("\nsleeping %d sec..." % SLEEP_SEC)
sleep(SLEEP_SEC)

print("\nDisabling shutter.")
common.send_cmd(dev, SET_CMD, 0)
common.verify_state(dev, GET_CMD, msb_len=1, expected=0, label="shutter")
