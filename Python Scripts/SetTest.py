import usb.core
import datetime
from time import sleep

# Newer ARM based products
dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

# Legacy products
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)

print dev
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
ZZ = [0,0,0,0,0,0,0,0]
TIMEOUT=1000

def Get_Value(Command, ByteCount):
	RetVal = 0
	RetArray = dev.ctrl_transfer(D2H, Command, 0,0,ByteCount,TIMEOUT)
	for i in range (0, ByteCount):
		RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
	return RetVal
	
def Test_Set(SetCommand, GetCommand, SetValue, RetLen):
	SetValueHigh = SetValue/0x10000
	SetValueLow = SetValue & 0xFFFF
	FifthByte = (SetValue >> 32) & 0xFF
	ZZ[0] = FifthByte
	Ret = dev.ctrl_transfer(H2D, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT) # set configuration
	if BUFFER_SIZE != Ret:
		return ('Set {0:x}	Fail'.format(SetCommand))
	else:
		RetValue = Get_Value(GetCommand, RetLen)
		if SetValue == RetValue:
			return ('Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))	
		else:
			return ('Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))	
	

# get ARM firmware version
#ARMVer = dev.ctrl_transfer(D2H, 0xc0, 0,0,5,TIMEOUT)   
#print ('ARM Ver 		{3:}{4:}.{2:}.{1:}.{0:}'.format(chr(ARMVer[0]+48), chr(ARMVer[1]+48),chr(ARMVer[2]+48), chr(ARMVer[3]+48-9),chr(ARMVer[3]+48-10)))

# get fpga rev
FPGAVer = dev.ctrl_transfer(D2H, 0xb4, 0,0,7,TIMEOUT)   
print ('FPGA Ver {0:}{1:}{2:}{3:}{4:}{5:}{6:}'.format(chr(FPGAVer[0]), chr(FPGAVer[1]), chr(FPGAVer[2]), chr(FPGAVer[3]), chr(FPGAVer[4]), chr(FPGAVer[5]), chr(FPGAVer[6])))

print '\nTesting Set Commands'
print "Integration Time	",		Test_Set(0xb2, 0xbf, 1, 6)
print "CCD Offset	", 		Test_Set(0xb6, 0xc4, 0, 2)
print "CCD Gain		",		Test_Set(0xb7, 0xc5, 487, 2)
