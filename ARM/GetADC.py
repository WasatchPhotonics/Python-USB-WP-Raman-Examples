#!/usr/bin/env python -u

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
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000

# select pixel count
#PixelCount = 512
PixelCount = 1024
#PixelCount = 2048

def Get_Value(Command, ByteCount, index=0):
	RetVal = 0
	RetArray = dev.ctrl_transfer(D2H, Command, 0,0,ByteCount,TIMEOUT)
	for i in range (0, ByteCount):
		RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
	return RetVal

while True:
	print "CCD Temperature		",	Get_Value(0xd7, 2),"		", 	dev.ctrl_transfer(D2H, 0xd7, 0,0,2,TIMEOUT)
	print "Laser Temperature	",	Get_Value(0xd5, 2),"		", 	dev.ctrl_transfer(D2H, 0xd5, 0,0,2,TIMEOUT)
	time.sleep(0.100)
