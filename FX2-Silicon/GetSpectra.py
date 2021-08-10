#!/usr/bin/env python -u

import usb.core
import datetime
import sys
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if dev is None:
    print("Unable to find spectrometer")
    sys.exit(-1)

print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z=[0] * BUFFER_SIZE
TIMEOUT=1000
MAX_SEC = 60

# select pixel count
PixelCount=1024

print("setting integration time to 100ms")
dev.ctrl_transfer(H2D, 0xb2, 100, 0, Z, TIMEOUT) # 100ms

start_time = datetime.datetime.now()

count = 0
while (datetime.datetime.now() - start_time).total_seconds() < MAX_SEC:
    # print("sending acquire")
    dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition

    cumulative_data = []
    total_bytes_needed = PixelCount * 2
    while len(cumulative_data) < total_bytes_needed:
        bytes_remaining = total_bytes_needed - len(cumulative_data)
        # print(f"requesting {bytes_remaining} bytes with timeout {TIMEOUT}ms")
        latest_data = dev.read(0x82, bytes_remaining, timeout=TIMEOUT)
        # print("read %d bytes (%d requested)" % (len(latest_data), bytes_remaining))
        cumulative_data.extend(latest_data)

    # print("read cumulative %d bytes" % len(cumulative_data))

    # marshall bytes back into uint16 pixels
    spectrum = []
    for i in range(PixelCount):
        lsb = cumulative_data[i*2]
        msb = cumulative_data[i*2 + 1]
        intensity = lsb | (msb << 8)
        spectrum.append(intensity)

    print("%4d %s: read spectrum of %d pixels: %s .. %s" % (count, datetime.datetime.now(), len(spectrum), spectrum[0:5], spectrum[-6:-1]))
    count += 1
            
