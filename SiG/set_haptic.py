#!/usr/bin/env python

import sys
import usb.core
import datetime
from time import sleep

# select product
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print ("No spectrometer found")
    sys.exit()
# print dev

H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000

def Get_Value(Command, command2, command3, ByteCount, index=0):
    RetArray = dev.ctrl_transfer(H2D, Command, command2, command3, ByteCount, TIMEOUT)

#    RetVal = 0

 #   RetVal = RetArray[-1]
    return RetArray
	
#raman_off = Get_Value(0xff, 0x16, 0x00, 2)

#haptic = Get_Value(0xff, 0x27, 0x0104, 1) #do longwarble 4 times
#haptic = Get_Value(0xff, 0x27, 0x0202, 1) #do 3 pulse 2 times
#haptic = Get_Value(0xff, 0x27, 0x030A, 1) #do shortwarble 10 times
#haptic = Get_Value(0xff, 0x27, 0x0406, 1) #do 1 pulse 6 times
haptic = Get_Value(0xff, 0x27, 0x0503, 1) #do 5 ticks 3 times
#haptic = Get_Value(0xff, 0x27, 0x0602, 1) #do warble pulse 2 times

