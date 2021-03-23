#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

import common

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if not dev:
    print("No spectrometers found")
    sys.exit()

GET_CMD = 0x35
TEST_COUNT = 5

def twos_comp(val, bits):
    if (val & (1 << (bits - 1))) != 0: # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val    

for i in range(TEST_COUNT):
    print("reading ambient temperature %d of %d" % (i + 1, TEST_COUNT))

    # read raw ambient temperature
    raw = common.get_cmd(dev, GET_CMD, msb_len=2)

    # convert to degrees Celsius
    msb = (raw >> 8) & 0xff
    lsb = raw & 0xff
    degC = 0.125 * twos_comp(raw, 11)

    print("ambient temperature %d of %d was 0x%04x raw (%0.2f degC)" % (i + 1, TEST_COUNT, raw, degC))
    sleep(1)
