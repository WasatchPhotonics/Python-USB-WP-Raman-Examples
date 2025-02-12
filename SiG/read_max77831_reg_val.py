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

MAX77831_3V3_ARM_DEV_ID=0x0f
MAX77831_5V0_LASER_DEV_ID=0x10

parser = argparse.ArgumentParser()
parser.add_argument("--d", type=lambda x: int(x, 16), help="device address in hex (0x0f or 0x10)")
parser.add_argument("--a", type=lambda x: int(x, 16), help="register address in hex")
args = parser.parse_args()


devAddr = 0x0
regAddr = 0xff

if args.d is None:
   print("specify device address in hex (0x0f or 0x10) !!")
   quit()
else:
   devAddr = args.d
   if devAddr != MAX77831_3V3_ARM_DEV_ID and devAddr != MAX77831_5V0_LASER_DEV_ID:
      print("specify device address in hex (0x0f or 0x10) !!")
      quit()
    
if args.a is None:
   print("specify register address (in hex) to read !!")
   quit()
else:
   regAddr = args.a


def Get_Value(Command, command2, ByteCount, param, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, param, 2, TIMEOUT_MS)

def read_reg(devAddr, regAddr):
    param = regAddr
    param <<= 8
    param |= devAddr
    data = Get_Value(0xff, 0x82, 2, param)
    # print(data)
    if data[0] != 0:
       print("Flr !! rc", data[0])
    else:
       val = data[1]
       print("0x{:02x} : 0x{:02x}".format(regAddr, val))
    return val      

read_reg(devAddr, regAddr)
