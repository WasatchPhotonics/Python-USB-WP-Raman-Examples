import sys
import usb.core
import datetime
from time import sleep

# Legacy products
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print "No spectrometer found"
    sys.exit()
# print dev

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
    return (RetVal, RetArray)

print "Integration Time   %8s %s" % Get_Value(0xbf, 6)
print "CCD Offset         %8s %s" % Get_Value(0xc4, 2)
print "CCD Gain           %8s %s" % Get_Value(0xc5, 2)
print "CCD Temp SP        %8s %s" % Get_Value(0xd9, 2)
print "CCD Temp ENABLE    %8s %s" % Get_Value(0xda, 1)
print "Laser Mod Duration %8s %s" % Get_Value(0xc3, 5)
print "Laser Mod Delay    %8s %s" % Get_Value(0xca, 5)
print "Laser Mod Period   %8s %s" % Get_Value(0xcb, 5)
print "Laser Diode Temp   %8s %s" % Get_Value(0xd5, 2)
print "Actual Int Time    %8s %s" % Get_Value(0xdf, 6)
print "CCD Temperature    %8s %s" % Get_Value(0xd7, 2)
print "Interlock          %8s %s" % Get_Value(0xef, 1)
