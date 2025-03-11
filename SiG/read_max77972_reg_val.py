#!/usr/bin/env python

import sys
import usb.core
import argparse

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

parser = argparse.ArgumentParser()
parser.add_argument("--a", type=lambda x: int(x, 16), help="register address in hex")
args = parser.parse_args()


regAddr = 0xffff

if args.a is None:
   print("specify register address (in hex) to read !!")
   quit()
else:
   regAddr = args.a


def Get_Value(Command, command2, ByteCount, regAddr, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, regAddr, 3, TIMEOUT_MS)

def read_reg(regAddr):
    data = Get_Value(0xff, 0x76, 3, regAddr)
    # print(data)
    if data[0] != 0:
       print("Flr !! rc", data[0])
    else:
       val = data[2]
       val <<= 8
       val |= data[1]
       print("{}/0x{:2x} : {}/0x{:04x}".format(regAddr, regAddr, val, val))
    return val      

read_reg(regAddr)
