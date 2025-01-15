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

USB_BC1PT2_adapterTypeTbl = ["Not found", "SDP", "CDP", "DCP"]
USB_BC1PT2_propAdapType = ["None", "Samsung 2A", "Apple 0.5 A", "Apple 1 A", "Apple 2 A", "Apple 12 W", "DCP 3A", "Unknown"]
USB_TYPE_C_CC_cap = ["Not Connected", "500 mA", "1500 mA", "3000 mA"]

def get_uint(bRequest, wValue, wIndex=0, lsb_len=5):
    return dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)

data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x78, 0, 5, TIMEOUT_MS)
print(data)
inLimCurrentMA = data[3] << 8
inLimCurrentMA += data[4]
print("")
print("BC1.2 Standard Adapter Type:", USB_BC1PT2_adapterTypeTbl[data[0]])
print("BC1.2 Proprietary Adapter Type:", USB_BC1PT2_propAdapType[data[1]])
print("Type C CC current Capability:", USB_TYPE_C_CC_cap[data[2]])
print("Adapter Input Limit Current:", inLimCurrentMA, "mA")
