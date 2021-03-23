#!/usr/bin/env python -u

import usb.core
import datetime
import time
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000

# select pixel count
#PixelCount=512
PixelCount=1024
#PixelCount=2048

print ("Start Data Acquisition...")
dev.ctrl_transfer(H2D, 0xad, 0,0,Z,TIMEOUT)   # trigger an acquisition

Data = dev.read(0x82,PixelCount*2)
for j in range (0, (PixelCount*2)<<8, 1):
	for i in range (0, 31, 2):
		NewData = Data[j*32+i+1]*256+Data[j*32+i]
		print (NewData)
