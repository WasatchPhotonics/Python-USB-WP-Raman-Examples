#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

#import common

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000

buf = [0] * 2

args = [0] * 5

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)

def print_help():
    print("-h / --help : Print help")
    print("arg1 : 0xC0 (IN) / 0x40 (OUT) (Hex)")
    print("arg2 : USB OPCODE (bRequest) (Hex)")
    print("arg3 : wValue (Hex)")  
    print("arg4 : wIndex (Hex)")
    sys.exit()

if not dev:
    print("No spectrometers found")
    sys.exit()

#if ((len(sys.argv) < 4) or (sys.argv[1] == "-h" or "--help")):
#    print_help()

for idx in range(1, len(sys.argv)) : 
    args[idx] = int(sys.argv[idx], 16)
    print(args[idx])

#print(sys.argv)
result = dev.ctrl_transfer(int(sys.argv[1], 16), int(sys.argv[2], 16), int(sys.argv[3], 16), int(sys.argv[4], 16), buf, TIMEOUT_MS) 
print(result)

exit