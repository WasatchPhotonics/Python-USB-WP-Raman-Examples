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
parser.add_argument("--str", type=str, help="string to insert (max 60 bytes)")
args = parser.parse_args()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)


input_str = args.str

buff1 = bytearray()
buff1.append(len(input_str))
buff2 = bytearray(input_str, 'utf-8')
buff1.extend(buff2)
print("len ", len(buff1))
print(buff1)

send_cmd(0xff, 0xa3, 0, buff1)

