import sys
import usb.core
import datetime
import time
from time import sleep

# select product
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print dev
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z=[0] * BUFFER_SIZE
TIMEOUT=1000

# select pixel count
#PixelCount=512
PixelCount=1024
#PixelCount=2048

print "Start Data Acquisition"
dev.ctrl_transfer(H2D, 0xad, 0,0,Z,TIMEOUT)   # trigger an acquisition

# MZ: this works from Windows but not Mac?
Data = dev.read(0x82, PixelCount*2)

print "Read %d pixels (%d bytes)" % (PixelCount, len(Data))
for j in range (0, (PixelCount*2)/32, 1):
    for i in range (0, 31, 2):
        pixel = Data[j*32+i+1]*256+Data[j*32+i]
        sys.stdout.write("%04x " % pixel)
    sys.stdout.write("\n")
