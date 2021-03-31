import usb.core
import datetime
import sys
import time

print ("Argument List:", str(sys.argv))
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)

print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
ZZ = [0,0,0,0,0,0,0,0]
TIMEOUT=1000


def Test_Set(SetCommand, SetValue):
	SetValueHigh = 0x0000
	SetValueLow = SetValue & 0xffff
	dev.ctrl_transfer(H2D, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT) # set configuration

Test_Set(0xd6, int(sys.argv[1]))
print("TEC set to: %s." % (sys.argv[1]))

# example usage:
# python TEC_control.py 0 
#(Sets TEC off))
# python TEC_control.py 1
#(Sets TEC on)