#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

import common

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if not dev:
    print("No spectrometers found")
    sys.exit()

SET_ACCY_EN         = 0x22

print("Accessory Connector Enabled")
common.send_cmd(dev, SET_ACCY_EN, 1)