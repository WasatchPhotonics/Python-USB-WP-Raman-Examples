#!/usr/bin/env python -u

import usb.core

# select product
dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
ZZ = [0,0,0,0,0,0,0,0]
TIMEOUT_MS = 1000

	
def Test_Set(SetCommand, value, RetLen):
	msw = (value << 16) & 0xffff
	lsw =  value        & 0xFFFF

	dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, lsw, msw, ZZ, TIMEOUT_MS)
			
print("Area Scan Ena", Test_Set(0xeb, 1, 1)) 
