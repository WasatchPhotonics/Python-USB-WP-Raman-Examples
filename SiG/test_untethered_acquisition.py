#!/usr/bin/env python

import os
import sys
import usb.core
import platform

from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUFFER_SIZE     = 8
BUF             = [0] * BUFFER_SIZE
TIMEOUT_MS      = 1000
INTEGRATION_MS  = 400
GAIN_DB         = 8
PIXELS          = 1952               # hardcoded for SiG IMX385

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

print(dev)

if os.name == "posix":
    dev.set_configuration()
    usb.util.claim_interface(dev, 0)

print("sending SET_INTEGRATION_TIME_MS -> %d ms" % INTEGRATION_MS)
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, INTEGRATION_MS, 0, BUF, TIMEOUT_MS)

gainDB = GAIN_DB << 8 # FunkyFloat(8.0)
print("sending GAIN_DB -> 0x%04x (FunkyFloat)" % gainDB)
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gainDB, 0, BUF, TIMEOUT_MS) 

print("sending ACQUIRE (untethered)")
try:
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 1, 0, BUF, TIMEOUT_MS)
except:
    print("ignoring timeout on untethered acquisition")

print("polling until IDLE")
while True:
    sleep(1)
    status = dev.ctrl_transfer(DEVICE_TO_HOST, 0xd4, 0, 0, 1, TIMEOUT_MS)[0]
    print(f"status = {status}")
    phase = ["IDLE", "DARK", "WARMUP", "SAMPLE", "PROCESSING", "ERROR"][status]
    print(f"phase = {phase}")
    if phase == "IDLE":
        break;

print("reading spectrum from EP2")
data = dev.read(0x82, PIXELS * 2) 

print("read %d bytes" % len(data))
if len(data) != PIXELS * 2:
    print("ERROR: read %d bytes" % len(data))
    sys.exit(1)

spectrum = []
for i in range(PIXELS):
    intensity = data[i*2] | (data[i*2 + 1] << 8) # demarshal LSB-MSB to uint16
    spectrum.append(intensity)

print(f"read {PIXELS} pixels from {spectrum[0:5]} to {spectrum[-6:]}")
