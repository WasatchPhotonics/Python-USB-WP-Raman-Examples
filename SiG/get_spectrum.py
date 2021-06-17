#!/usr/bin/env python

import os
import sys
import usb.core
import platform

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUFFER_SIZE     = 8
BUF             = [0] * BUFFER_SIZE
TIMEOUT_MS      = 1000
INTEGRATION_MS  = 1
PIXELS          = 1952               # hardcoded for SiG IMX385/392

print("os %s, platform %s (%s)" % (os.name, platform.system(), platform.release()))

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

if os.name == "posix":
    dev.set_configuration()
    usb.util.claim_interface(dev, 0)

print("sending SET_INTEGRATION_TIME_MS -> %d ms" % INTEGRATION_MS)
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, INTEGRATION_MS, 0, BUF, TIMEOUT_MS)

gainDB = 0x0100 # FunkyFloat(1.0)
print("sending GAIN_DB -> 0x%04x (FunkyFloat)" % gainDB)
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gainDB, 0, BUF, TIMEOUT_MS) 

print("sending ACQUIRE")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

print("reading spectrum from bulk endpoint")
data = dev.read(0x82, PIXELS * 2) # each pixel is uint16

print("successfully read %d bytes" % len(data))
for i in range(PIXELS):
    value = data[i*2] | (data[i*2 + 1] << 8) # demarshal LSB-MSB to uint16
    print("pixel %4d: 0x%04x (%d)" % (i, value, value))
