#!/usr/bin/env python -u

import usb.core
import datetime
import time
from time import sleep

MAX_TIME_SEC = 1
INTEG_TIME_MS = 10 

def dump_hex(a):
    print('[{}]'.format(', '.join(hex(x) for x in a)))

def dump_csv(start, a):
    for i in range(len(a) // 2):
        lsb = a[i*2]
        msb = a[i*2 + 1]
        intensity = lsb | (msb << 8)
        print("%d, %d" % (start + i, intensity))

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)

# print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z=[0] * BUFFER_SIZE
TIMEOUT=1000

# select pixel count
PixelCount=1024

# print("setting integration time to %d ms" % INTEG_TIME_MS)
# dev.ctrl_transfer(H2D, 0xb2, INTEG_TIME_MS, 0, Z, TIMEOUT) # 100ms

start_time = datetime.datetime.now()
spectra_count = 0

while (datetime.datetime.now() - start_time).total_seconds() < MAX_TIME_SEC:

    print("sending acquire\n")
    dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition

    BLOCK_SIZE = 64

    cumulative_data = []
    total_bytes_needed = PixelCount * 2
    pixel_index = 0 # for CSV output
    while len(cumulative_data) < total_bytes_needed:
        bytes_remaining = total_bytes_needed - len(cumulative_data)
        latest_data = dev.read(0x82, BLOCK_SIZE, timeout=TIMEOUT)
        cumulative_data.extend(latest_data)

        # aggregate an ongoing CSV as we read blocks
        # dump_csv(pixel_index, latest_data)
        pixel_index += len(latest_data) // 2

    print("read cumulative %d bytes" % len(cumulative_data))

    # marshall bytes back into uint16 pixels
    spectrum = []
    for i in range(PixelCount):
        lsb = cumulative_data[i*2]
        msb = cumulative_data[i*2 + 1]
        intensity = lsb | (msb << 8)
        spectrum.append(intensity)

    print("read spectrum of %d pixels: %s .. %s" % (len(spectrum), spectrum[0:5], spectrum[-6:-1]))
    spectra_count += 1
        
elapsed_sec = (datetime.datetime.now() - start_time).total_seconds()
print("Read %d spectra in %.2f sec", spectra_count, elapsed_sec)
print("Scan rate = %.2f Hz", (spectra_count / elapsed_sec) / 60.0)
