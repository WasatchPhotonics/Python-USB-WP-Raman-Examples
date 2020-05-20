#!/usr/bin/env python -u

import sys
import usb.core
import datetime
import time
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

pixels = 1952
integration_time_ms = 10

# report firmware revisions
fw = ".".join(reversed([str(x) for x in dev.ctrl_transfer(DEVICE_TO_HOST, 0xc0, 0, 0, 64)]))
fpga = "".join([chr(x) for x in dev.ctrl_transfer(DEVICE_TO_HOST, 0xb4, 0, 0, 64)])
print("FW %s FPGA %s" % (fw, fpga))

print("Set integration time 10ms")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, integration_time_ms & 0xffff, 0, Z, TIMEOUT_MS)

print("Enable area scan")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xeb, 1, 0, Z, TIMEOUT_MS)

print("Looping over 20 rows")
spectra_to_read = 20
for count in range(spectra_to_read):
    # send SW trigger
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, Z, TIMEOUT_MS)

    # read spectrum
    data = dev.read(0x82, pixels * 2)

    spectrum = []
    for i in range(0, len(data), 2):
        spectrum.append(data[i] | (data[i+1] << 8))

    print("Spectrum %3d/%3d: %s ..." % (count + 1, spectra_to_read, spectrum[:10]))
