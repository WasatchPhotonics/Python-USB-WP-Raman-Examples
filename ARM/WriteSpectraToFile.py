#!/usr/bin/env python -u

import usb.core
import datetime
import time
from time import sleep

# Newer ARM based products
dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

# Legacy products
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)

print dev
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000

PixelCount = 1024

file = open("data.csv","w")

while True:
	print "Start Data Acquisition"
	dev.ctrl_transfer(H2D, 0xad, 0,0,Z,TIMEOUT)   # trigger an acquisition

	Data = dev.read(0x82,PixelCount*2)
	for j in range (0, (PixelCount*2)/32, 1):
		for i in range (0, 31, 2):
			NewData = Data[j*32+i+1]*256+Data[j*32+i]
			file.write(str(NewData))
			file.write(",")
	file.write('\n')
	time.sleep(2)
