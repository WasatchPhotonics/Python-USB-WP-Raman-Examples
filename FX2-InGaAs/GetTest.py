import usb.core
import datetime
from time import sleep

OUTPUT_TYPE = "NUMERIC"
#OUTPUT_TYPE = "ARRAY"

# Legacy products
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print(dev)
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

if OUTPUT_TYPE == "ARRAY":
	# Array output
	print("Integration Time	        ",	dev.ctrl_transfer(D2H, 0xbf, 0,0,6,TIMEOUT))
	print("CCD Offset		", 	dev.ctrl_transfer(D2H, 0xc4, 0,0,2,TIMEOUT))
	print("CCD Gain		        ", 	dev.ctrl_transfer(D2H, 0xc5, 0,0,2,TIMEOUT))
	print("CCD Temperature SP	", 	dev.ctrl_transfer(D2H, 0xd9, 0,0,2,TIMEOUT))
	print("Laser Mod Duration	",	dev.ctrl_transfer(D2H, 0xc3, 0,0,5,TIMEOUT))
	print("Laser Mod Delay		",	dev.ctrl_transfer(D2H, 0xca, 0,0,5,TIMEOUT))
	print("Laser Mod Period	        ",	dev.ctrl_transfer(D2H, 0xcb, 0,0,5,TIMEOUT))
	print("Number of Frames	        ",	dev.ctrl_transfer(D2H, 0xcd, 0,0,1,TIMEOUT))
	print("Data Thresdhold		",	dev.ctrl_transfer(D2H, 0xd1, 0,0,2,TIMEOUT))
	print("Laser Diode Temp	        ",	dev.ctrl_transfer(D2H, 0xd5, 0,0,2,TIMEOUT))
	print("Actual Int Time		",	dev.ctrl_transfer(D2H, 0xdf, 0,0,6,TIMEOUT))
	print("CCD Temperature		",	dev.ctrl_transfer(D2H, 0xd7, 0,5,4,TIMEOUT))
else:
	# Numerical output
	print("Integration Time	        ",	Get_Value(0xbf, 6),	"		", 	dev.ctrl_transfer(D2H, 0xbf, 0,0,6,TIMEOUT))
	print("CCD Offset		", 	Get_Value(0xc4, 2),	"		", 	dev.ctrl_transfer(D2H, 0xc4, 0,0,2,TIMEOUT))
	print("CCD Gain		        ", 	Get_Value(0xc5, 2),	"		", 	dev.ctrl_transfer(D2H, 0xc5, 0,0,2,TIMEOUT))
	print("CCD Temp SP		", 	Get_Value(0xd9, 2),	"		", 	dev.ctrl_transfer(D2H, 0xd9, 0,0,2,TIMEOUT))
	print("CCD Temp ENABLE		", 	Get_Value(0xda, 1),	"		", 	dev.ctrl_transfer(D2H, 0xda, 0,0,1,TIMEOUT))
	print("Laser Mod Duration	",	Get_Value(0xc3, 5),	"		",	dev.ctrl_transfer(D2H, 0xc3, 0,0,5,TIMEOUT))
	print("Laser Mod Delay		",	Get_Value(0xca, 5),	"		",	dev.ctrl_transfer(D2H, 0xca, 0,0,5,TIMEOUT))
	print("Laser Mod Period	        ",	Get_Value(0xcb, 5),	"		", 	dev.ctrl_transfer(D2H, 0xcb, 0,0,5,TIMEOUT))
	print("Laser Diode Temp	        ",	Get_Value(0xd5, 2),	"		", 	dev.ctrl_transfer(D2H, 0xd5, 0,0,2,TIMEOUT))
	print("Actual Int Time		",	Get_Value(0xdf, 6),	"		", 	dev.ctrl_transfer(D2H, 0xdf, 0,0,6,TIMEOUT))
	print("CCD Temperature		",	Get_Value(0xd7, 2),"		", 	dev.ctrl_transfer(D2H, 0xd7, 0,0,2,TIMEOUT))
