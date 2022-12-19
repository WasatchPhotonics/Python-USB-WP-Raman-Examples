#!/usr/bin/env python -u

import sys
import usb.core
import datetime
import time
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

pixels = 512


def get_raw(bRequest, wValue=0, wIndex=0, length=64):
    return dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, length, TIMEOUT_MS)

def get_enabled():
    print("Getting High-Gain Mode: ", end='')
    print(get_raw(0xec))

def set_enabled(flag=True):
    print(f"Setting High-Gain Mode = {flag}")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xeb, 1 if flag else 0, 0, Z, TIMEOUT_MS)

def get_spectra():
    for count in range(3): # throwaways
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, Z, TIMEOUT_MS)
        data = dev.read(0x82, pixels * 2)
        spectrum = []
        for i in range(pixels):
            pixel = data[i*2] | (data[i*2 + 1] << 8)
            spectrum.append(pixel)
        mean = sum(spectrum) / pixels            
        print(f"spectrum (mean {mean:0.2f}): {spectrum[:3]} .. {spectrum[-3:]}")

print("FX2 FW Version %s" % ".".join(str(x) for x in list(reversed(list(get_raw(0xc0, length=4))))))
print("FPGA FW Version %s" % "".join(chr(c) for c in get_raw(0xb4, length=7)))

print("\ninitial conditions")
get_enabled()
get_spectra()

print("\nenabling")
set_enabled(True)
get_enabled()
get_spectra()

print("\ndisabling")
set_enabled(False)
get_enabled()
get_spectra()
