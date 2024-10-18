#!/usr/bin/env python

import sys
import usb.core
from datetime import datetime

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def get_uint(bRequest, wValue, wIndex=0, lsb_len=4):
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
    # print(f"<< {data}")
    value = 0
    for i in range(lsb_len):
        value |= (data[i] << i)
    # print(f"returning 0x{value:04x} ({value})")
    return value


def get_tec_dac_state():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x60, 0, 1, TIMEOUT_MS)
    tecDACState = data[0]
    if tecDACState == 0:
       print("TEC DAC is Off")
    else:
       print("TEC DAC is On")
    return tecDACState

def get_tec_mode():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x61, 0, 1, TIMEOUT_MS)
    tecMode= data[0]
    print("TEC mode ", tecMode, " [0: Off, 1: On, 2: Auto, 3: Auto-On]")
    return tecMode

def get_tec_state():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0x85, 0x00, 0, 1, TIMEOUT_MS)
    tecState = data[0]
    print("TEC state is ", tecState)
    if tecState == 0:
       print("TEC is Off")
    else:
       print("TEC is On")
    return tecState

def get_laser_state():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xe2, 0, 0, 1, TIMEOUT_MS)
    laserState = data[0]
    if laserState == 0:
       print("LASER is Off")
    else:
       print("LASER is On")
    return laserState

print()


get_laser_state()
get_tec_state()
get_tec_dac_state()
get_tec_mode()
