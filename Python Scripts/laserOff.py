import usb.core
import datetime
from time import sleep

# Newer ARM based products
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)

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
	Ret = dev.ctrl_transfer(H2D, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT)# set configuration
	if BUFFER_SIZE != Ret:
		return ('Set {0:x}	Fail'.format(SetCommand))
	else:
		RetValue = Get_Value(GetCommand, RetLen)
		if SetValue == RetValue:
			return ('Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))	
		else:
			return ('Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))	
			
print "Laser Off", 		Test_Set(0xbe, 0xe2, 0, 1)
