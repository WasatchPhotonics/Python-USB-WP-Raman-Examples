#!/usr/bin/env python -u

import usb.core
import datetime
import sys
import time
from time import sleep
import matplotlib.pyplot as plt
import struct

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)
if dev is None:
    print("Unable to find spectrometer")
    sys.exit(-1)

print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=1
Z=[0] * BUFFER_SIZE
TIMEOUT=15000
MAX_SEC = 1000
INTEG_MS = 235

# select pixel count
PixelCount=2592*1944

#print("setting integration time to %d ms" % INTEG_MS)
#dev.ctrl_transfer(H2D, 0xb2, INTEG_MS, 0, Z, TIMEOUT) 

start_time = datetime.datetime.now()

firstSegRcvd = 0
count = 0
while (datetime.datetime.now() - start_time).total_seconds() < MAX_SEC:
    print("sending acquire")
    # dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition
    data = dev.ctrl_transfer(D2H, 0xb4, 0, 0, 1, TIMEOUT)
    print("reading data from EP 0x82 .....\n")

    ts0 = time.time()
    print("TS0:", ts0)
    cumulative_data = []
    total_bytes_needed = PixelCount*2 
    while len(cumulative_data) < total_bytes_needed:
        bytes_remaining = total_bytes_needed - len(cumulative_data)
        #print(f"requesting {bytes_remaining} bytes with timeout {TIMEOUT}ms")
        latest_data = dev.read(0x82, bytes_remaining, timeout=TIMEOUT)
        if firstSegRcvd == 0:
            print("first seg sz rcvd", len(latest_data))
            ts1 = time.time()
            print("TS1:", ts1)
            firstSegRcvd = 1
        # print("read %d bytes (%d requested)" % (len(latest_data), bytes_remaining))
        # print(bytes_remaining)
        cumulative_data.extend(latest_data)

    print("Rcvd image ..")
    ts2 = time.time()
    #print("TS0:", ts0)
    #print("TS1:", ts1)
    print("TS2:", ts2)
    print("TS1-TS0 =", ts1 - ts0)
    print("TS2-TS1 =", ts2 - ts1)
    print("TS2-TS0 =", ts2 - ts0)
    
    # print("read cumulative %d bytes" % len(cumulative_data))

    # marshall bytes back into uint16 pixels
    spectrum = []
    for i in range(PixelCount):
        lsb = cumulative_data[i*2]
        msb = cumulative_data[i*2 + 1]
        intensity = lsb | (msb << 8)
        spectrum.append(intensity)

    # x_axis = []
    # for i in range(PixelCount):
    #   x_axis.append(i)

    print("Rcvd spectrum with pixel cnt", len(spectrum))
    print(hex(spectrum[0]), 
          hex(spectrum[1]),
          hex(spectrum[2]),
          hex(spectrum[3]),
          hex(spectrum[4]),
          hex(spectrum[5]),
          hex(spectrum[6]),
          hex(spectrum[7]))
    pixCnt = len(spectrum)
    print(hex(spectrum[pixCnt-8]), 
          hex(spectrum[pixCnt-7]),
          hex(spectrum[pixCnt-6]),
          hex(spectrum[pixCnt-5]),
          hex(spectrum[pixCnt-4]),
          hex(spectrum[pixCnt-3]),
          hex(spectrum[pixCnt-2]),
          hex(spectrum[pixCnt-1]))
    packed_bytes = b"".join([struct.pack('B', byte_val) for byte_val in cumulative_data])

    file_path = "raw10.bin"
    with open(file_path, "wb") as f:
      f.write(packed_bytes)
      print(f"Binary array saved to {file_path}")
      f.close()

    # if count == 1:
    #    plt.plot(x_axis, spectrum)
    #    plt.show()
    #    break
    # print("%4d %s: read spectrum of %d pixels: %s .. %s" % (count, datetime.datetime.now(), len(spectrum), spectrum[0:5], spectrum[-6:-1]))

    count += 1
    if count >= 1:
       break
