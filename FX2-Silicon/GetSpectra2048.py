#!/usr/bin/env python -u

import usb.core
import sys

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if dev is None:
    print( "No spectrometer found")
    sys.exit()
print (dev)

H2D=0x40
D2H=0xC0
Z = [0] * 8
TIMEOUT=1000

# select pixel count
PixelCount = 2048
ByteCount = PixelCount * 2 # 16-bit pixels

print({ "Start Data Acquisition..."})
dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition

spectrum = []
for endpoint in (0x82, 0x86):
    data = dev.read(endpoint, (int)(ByteCount / 2)) # we only read half the data from each endpoint
    pixels = [i + 256 * j for i, j in zip(data[::2], data[1::2])]
    spectrum.extend(pixels)

for index in range(len(spectrum)):
    print ("Pixel %4d: %5d" % (index, spectrum[index]))
