import usb.core
import datetime
import time
from time import sleep

# Select product
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print(dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
ZZ = [0,0,0,0,0,0,0,0]
TIMEOUT=1000
frameCounter = 0

# select pixel count
PixelCount=512
#PixelCount=1024
#PixelCount=2048


file = open("data.csv","w")

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
print("Turn OFF Continuous Read	",		Test_Set(0xc8, 0xcc, 0, 1))
print("Set the Number of Frames	",		Test_Set(0xc9, 0xcd, 1, 1))
print("Capturing... (60 second timeout)")
while(1):
        stringBuffer = ""
        frameCounter = frameCounter + 1
        Data = dev.read(0x82,PixelCount*2,60000)
        ts = time.time()
        stringBuffer = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S %f')
        stringBuffer = stringBuffer + ","
        for j in range (0, (PixelCount*2)/32, 1):
		for i in range (0, 31, 2):
			NewData = Data[j*32+i+1]*256+Data[j*32+i]
			stringBuffer = stringBuffer + str(NewData)
			stringBuffer = stringBuffer + ","
	stringBuffer = stringBuffer + '\n'
        file.write(stringBuffer)
        # Print frame number to console, must be commented out when sampling
        # at a rate greater than 100Hz to maintain data integrity
        #print("Frame : {}".format(frameCounter)) 



