#!/usr/bin/env python -u

import usb.core
import datetime
import sys
from time import sleep
import matplotlib.pyplot as plt

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
TIMEOUT=90000
MAX_SEC = 1000
INTEG_MS = 235

# select pixel count
PixelCount=2048

print("setting integration time to %d ms" % INTEG_MS)
dev.ctrl_transfer(H2D, 0xb2, INTEG_MS, 0, Z, TIMEOUT) 

start_time = datetime.datetime.now()

count = 0
while (datetime.datetime.now() - start_time).total_seconds() < MAX_SEC:
    # print("sending acquire")
    dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition

    print("reading data from EP 0x82 .....\n")

    cumulative_data = []
    total_bytes_needed = (PixelCount*2)/2 
    while len(cumulative_data) < total_bytes_needed:
        bytes_remaining = total_bytes_needed - len(cumulative_data)
        print(f"requesting {bytes_remaining} bytes with timeout {TIMEOUT}ms")
        latest_data = dev.read(0x82, bytes_remaining, timeout=TIMEOUT)
        print("read %d bytes (%d requested)" % (len(latest_data), bytes_remaining))
        cumulative_data.extend(latest_data)
    
    print("reading data from EP 0x86 .....\n")

    cumulative_data_1 = []
    total_bytes_needed = PixelCount 
    while len(cumulative_data_1) < total_bytes_needed:
        bytes_remaining = total_bytes_needed - len(cumulative_data_1)
        print(f"requesting {bytes_remaining} bytes with timeout {TIMEOUT}ms")
        latest_data = dev.read(0x86, bytes_remaining, timeout=TIMEOUT)
        print("read %d bytes (%d requested)" % (len(latest_data), bytes_remaining))
        cumulative_data_1.extend(latest_data)
        cumulative_data.extend(latest_data)

    # print("read cumulative %d bytes" % len(cumulative_data))

    # marshall bytes back into uint16 pixels
    spectrum = []
    for i in range(PixelCount):
        lsb = cumulative_data[i*2]
        msb = cumulative_data[i*2 + 1]
        intensity = lsb | (msb << 8)
        spectrum.append(intensity)

    x_axis = []
    for i in range(PixelCount):
      x_axis.append(i)

    if count == 1:
       plt.plot(x_axis, spectrum)
       plt.show()
       break
    print("%4d %s: read spectrum of %d pixels: %s .. %s" % (count, datetime.datetime.now(), len(spectrum), spectrum[0:5], spectrum[-6:-1]))

    count += 1
    if count >= 2:
       break
