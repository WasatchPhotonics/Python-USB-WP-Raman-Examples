#!/usr/bin/env python

import sys
import usb.core

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000
VR_GET_SPECTRA_LINE_FRAME_HDR_CFG = 0x99

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

cfg = Get_Value(VR_GET_SPECTRA_LINE_FRAME_HDR_CFG, 0x0, 1)
print(cfg)
