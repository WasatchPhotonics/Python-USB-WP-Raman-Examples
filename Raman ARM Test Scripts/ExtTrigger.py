import usb.core
import datetime
from time import sleep

# select product
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print dev
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
ZZ = [0,0,0,0,0,0,0,0]
TIMEOUT=1000
frameCounter = 0

# select pixel count 
#PixelCount=512
PixelCount=1024
#PixelCount=2048

print dev

def Get_Value(Command, ByteCount):
	RetVal = 0
	RetArray = dev.ctrl_transfer(0xC0, Command, 0,0,ByteCount,1000)
	for i in range (0, ByteCount):
		RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
	return RetVal

def Test_Set(SetCommand, GetCommand, SetValue, RetLen):
	SetValueHigh = SetValue/0x10000
	SetValueLow = SetValue & 0xFFFF
	FifthByte = (SetValue >> 32) & 0xFF
	ZZ[0] = FifthByte
	Ret = dev.ctrl_transfer(H2D, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT)# set configuration
	if BUFFER_SIZE != Ret:
		return ('Set {0:x}	Fail'.format(SetCommand))
	else:
		RetValue = Get_Value(GetCommand, RetLen)
		if SetValue == RetValue:
			return ('Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))	
		else:
			return ('Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))	

# Set the Integration time to 1ms
print "Integration Time	",		Test_Set(0xb2, 0xbf, 1, 6)
print "Waiting for data... (60 second timeout)"

while(1):        
        frameCounter = frameCounter + 1
        Data = dev.read(0x82,PixelCount*2,60000)
        print("Frame : {}".format(frameCounter)) # Print frame number to console



