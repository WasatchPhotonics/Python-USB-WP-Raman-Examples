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
TIMEOUT=1000
MAX_SEC = 1000
INTEG_MS = 100
# select pixel count
PixelCount=1024*2
LineCount=70

print("setting integration time to %d ms" % INTEG_MS)
dev.ctrl_transfer(H2D, 0xb2, INTEG_MS, 0, Z, TIMEOUT) 

start_time = datetime.datetime.now()

linesReadCnt = 0
count = 0
prevLineCnt = 0
bytesReadTot = 0
cumulative_data = []
#while (datetime.datetime.now() - start_time).total_seconds() < MAX_SEC:
print("Line Count is", LineCount)
print("sending acquire")
dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition

while (1):
    bytesReadTot = 0

    total_bytes_needed = (PixelCount * 2) 

    print("Line #{}, Reading EP 0x82 .... ".format(linesReadCnt+1))
    while bytesReadTot < total_bytes_needed/2:
        bytes_remaining = int(total_bytes_needed/2 - bytesReadTot)
        print("rem", bytes_remaining)
        #print(f"requesting {bytes_remaining} bytes with timeout {TIMEOUT}ms")
        latest_data = dev.read(0x82, bytes_remaining, timeout=TIMEOUT)
        #print("read %d bytes (%d requested)" % (len(latest_data), bytes_remaining))
        cumulative_data.extend(latest_data) 
        bytesReadTot += len(latest_data)
        print("tot read", bytesReadTot)

   
    print("Line #{}, Reading EP 0x86 .... ".format(linesReadCnt+1))
    while bytesReadTot < total_bytes_needed:
        bytes_remaining = int(total_bytes_needed - bytesReadTot)
        print("rem", bytes_remaining)
        #print(f"requesting {bytes_remaining} bytes with timeout {TIMEOUT}ms")
        latest_data = dev.read(0x86, bytes_remaining, timeout=TIMEOUT)
        #print("read %d bytes (%d requested)" % (len(latest_data), bytes_remaining))
        cumulative_data.extend(latest_data) 
        bytesReadTot += len(latest_data)
        print("tot read", bytesReadTot)



    linesReadCnt += 1

    print("read cumulative %d bytes" % len(cumulative_data))
    print("lines read {}/{}".format(linesReadCnt, LineCount))

    if linesReadCnt >= LineCount:
        break

# marshall bytes back into uint16 pixels
spectrum = []
offset = 0

for i in range(LineCount):
    lsb0 = cumulative_data[offset]
    msb0 = cumulative_data[offset + 1]
    intensity0 = lsb0 | (msb0 << 8)

    lsb1 = cumulative_data[offset + 2]
    msb1 = cumulative_data[offset + 3]
    intensity1 = lsb1 | (msb1 << 8)
        
    print(offset, ":", intensity0, "/", intensity1)

    offset += (PixelCount*2)


