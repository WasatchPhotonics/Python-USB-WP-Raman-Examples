#!/usr/bin/env python -u

import usb.core
import datetime
from time import sleep

# Product selection
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000

def Get_Value(Command, Command2, ByteCount, index=0):
	RetVal = 0
	RetArray = dev.ctrl_transfer(D2H, Command, Command2, 0, ByteCount, TIMEOUT)
	for i in range (0, ByteCount):
		RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
	return RetVal


print ("Lasing Status:		",	Get_Value(0xff, 0x0D, 1),"		", 	dev.ctrl_transfer(D2H, 0xff, 0x0D,0,1,TIMEOUT))
