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
parser.add_argument("--v", type=lambda x: int(x, 16), help="register value in hex")
args = parser.parse_args()

devAddr = 0x0
regAddr = 0x0
regVal = 0x0

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

if args.v is None:
   print("specify register value (in hex) to write !!")
   quit()
else:
   regVal = args.v

def send_cmd(buf):
    # print(buf)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0x83, 0, buf, TIMEOUT_MS)
 
def write_reg(devAddr, regAddr, regVal):
    buf = [0] * 6

    print(devAddr, regAddr, regVal);

    buf[0] = devAddr & 0xff
    devAddr >>= 8
    buf[1] = devAddr & 0xff

    buf[2] = regAddr & 0xff
    regAddr >>= 8
    buf[3] = regAddr & 0xff

    buf[4] = regVal & 0xff
    regVal >>= 8
    buf[5] = regVal & 0xff

    send_cmd(buf)

write_reg(devAddr, regAddr, regVal)
print('done')
