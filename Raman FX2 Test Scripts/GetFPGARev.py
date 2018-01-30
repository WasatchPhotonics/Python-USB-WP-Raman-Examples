import usb.core
import datetime
from time import sleep

# Select Product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print dev
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000

def Get_Value(Command, ByteCount, index=0):
	RetVal = 0
	RetArray = dev.ctrl_transfer(D2H, Command, 0,0,ByteCount,TIMEOUT)
	for i in range (0, ByteCount):
		RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
	return RetVal

FPGAVer = dev.ctrl_transfer(D2H, 0xb4, 0,0,7,TIMEOUT)   
print ('FPGA Ver 		{0:}{1:}{2:}{3:}{4:}{5:}{6:}'.format(chr(FPGAVer[0]), chr(FPGAVer[1]), chr(FPGAVer[2]), chr(FPGAVer[3]), chr(FPGAVer[4]), chr(FPGAVer[5]), chr(FPGAVer[6])))
	
