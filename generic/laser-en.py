#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

#import common

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000

VR_SET_LASER = 0xBE

buf = [0] * 2

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)

def print_help():
    print("-h : Print help")

if not dev:
    print("No spectrometers found")
    sys.exit()

if sys.argv[1] == "-h":
    print_help()

elif int(sys.argv[1]) == 1:             
    result = dev.ctrl_transfer(HOST_TO_DEVICE, VR_SET_LASER, 1, 0, buf, TIMEOUT_MS)

else:
     result = dev.ctrl_transfer(HOST_TO_DEVICE, VR_SET_LASER, 0, 0, buf, TIMEOUT_MS)
