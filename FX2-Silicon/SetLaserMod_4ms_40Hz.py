#!/usr/bin/env python -u

import usb.core

dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
ZZ = [0,0,0,0,0,0,0,0]
TIMEOUT_MS = 1000

def Get_Value(Command, ByteCount):
    RetVal = 0
    RetArray = dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, TIMEOUT_MS)
    for i in range(ByteCount):
        RetVal = (RetVal << 8) | RetArray[ByteCount - i - 1]
    return RetVal
    
# note that this does NOT send the extra "fake payload" buffers
def Test_Set(SetCommand, GetCommand, value, RetLen):
    msw = (value >> 16) & 0xffff
    lsw =  value        & 0xffff
    Ret = dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, lsw, msw, ZZ, TIMEOUT_MS)
    if BUFFER_SIZE != Ret:
        return ('Set {0:x}  Fail'.format(SetCommand))
    else:
        RetValue = Get_Value(GetCommand, RetLen)
        if value == RetValue:
            return ('Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, value, RetValue))    
        else:
            return ('Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, value, RetValue))    
            
print("Laser Mod Pulse Period", Test_Set(0xc7, 0xcb, 25000, 5)) # Sets the modulation period to 25ms
print("Laser Mod Pulse Width",  Test_Set(0xdb, 0xdc,  4000, 5)) # Sets the modulation pulse-width to 4ms
print("Laser Mod Enable",       Test_Set(0xbd, 0xe3,     1, 1)) # Enables laser modulation
print("Laser ON",               Test_Set(0xbe, 0xe2,     1, 1)) # Turn the laser ON
