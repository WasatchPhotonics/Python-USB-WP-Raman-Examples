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
	print "Photodiode RAW	",	Get_Value(0xa6, 3),"		", 	dev.ctrl_transfer(D2H, 0xa6, 0,0,3,TIMEOUT)
	time.sleep(0.100)
