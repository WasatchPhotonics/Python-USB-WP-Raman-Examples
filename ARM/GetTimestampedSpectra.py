#!/usr/bin/env python -u

import usb.core
import datetime
import sys

from time import sleep

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)
if dev is None:
    print("No spectrometers found")
    sys.exit(0)

print dev
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS=1000

PixelCount=1024
PixelCount=1952

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
    ZZ = [0] * BUFFER_SIZE
    ZZ[0] = FifthByte
    Ret = dev.ctrl_transfer(H2D, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT_MS)# set configuration
    if BUFFER_SIZE != Ret:
        return ('Set {0:x}  Fail'.format(SetCommand))
    else:
        RetValue = Get_Value(GetCommand, RetLen)
        if SetValue == RetValue:
            return ('Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))    
        else:
            return ('Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))    

# set integration time to 10ms
integration_time_ms = 10
print("Setting integration time to %d ms" % integration_time_ms)
print Test_Set(0xb2, 0xbf, integration_time_ms, 6)

for count in range(100):
    timeStart = datetime.datetime.now()
    dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT_MS)   # trigger an acquisition
    Data = dev.read(0x82,PixelCount*2)
    spectrum = []
    for j in range (0, (PixelCount*2)/32, 1):
        for i in range (0, 31, 2):
            spectrum.append(Data[j*32+i] | (Data[j*32+i+1] << 8))
    timeEnd = datetime.datetime.now()
    sec = (timeEnd - timeStart).total_seconds()

    print("%s spectrum %3d: read %d pixels at %d ms in %.3f sec" % (timeEnd, count, len(spectrum), integration_time_ms, sec))

    # 65-75ms seems to be the threshold (sometimes works, sometimes fails)
    sleep(0.1)
