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
parser.add_argument("--v", type=lambda x: int(x, 16), help="register value in hex")
args = parser.parse_args()


regAddr = 0x0
regVal = 0x0

if args.v is None:
   print("specify register value to write !!")
   quit()
else:
   regVal = args.v

if args.a is None:
   print("specify register address to update !!")
   quit()
else:
   regAddr = args.a

def send_cmd(buf):
    # print(buf)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0x75, 0, buf, TIMEOUT_MS)
 
def write_reg(regAddr, regVal):
    buf = [0] * 4
    buf[0] = regAddr & 0xff
    regAddr >>= 8
    buf[1] = regAddr & 0xff

    buf[2] = regVal & 0xff
    regVal >>= 8
    buf[3] = regVal & 0xff

    send_cmd(buf)

write_reg(regAddr, regVal)
print('done')
