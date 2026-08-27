#!/usr/bin/env python


import sys
import usb.core
import argparse
import platform

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000, backend=backend.get_backend())

# dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
   print("No spectrometer found")
   sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

regAddr = 0xffff

def Get_Value(Command, command2, ByteCount, regAddr, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, regAddr, 3, TIMEOUT_MS)

def read_reg(regAddr):
    #print(regAddr)
    data = Get_Value(0xff, 0x76, 3, regAddr)
    # print(data)
    val = 0
    if data[0] != 0:
       print("Flr !! rc", data[0])
    else:
       val = data[2]
       val <<= 8
       val |= data[1]
       #print("{}/0x{:2x} : {}/0x{:04x}".format(regAddr, regAddr, val, val))
       print("0x{:04x} : 0x{:04x}".format(regAddr, val))
    return val      


extRegList = [
  0x19d,
  0x1a6,
  0x1a7,
  0x1ab,
  0x1b6,
  0x1b7,
  0x1ba,
  0x1bb,
  0x1c2,
  0x1c4,
  0x1c5,
  0x1c7,
  0x1c8,
  0x1c9,
  0x1ca,
  0x1cc,
  0x1cd,
  0x1ce,
  0x1cf,
  0x1d1,
  0x1d5,
  0x1d6,
  0x1d7,
  0x1dc,
  0x1e1,
  0x1e3
]

skipList = [
 0x2,
 0x11,
 0x13,
 0x15,
 0x1e,
 0x20,
 0x2b,
 0x2c,
 0x2d,
 0x30,
 0x31,
 0x33,
 0x36,
 0x37,
 0x38,
 0x3b,
 0x40,
 0x41,
 0x43,
 0x44,
 0x47,
 0x48,
 0x49,
 0x4a,
 0x4b,
 0x4c,
 0x4e,
 0x4f,
 0x50
]

for regAddr in range(83):
    if regAddr in skipList:
       continue
    read_reg(regAddr)

for regAddr in range(128, 160):
    read_reg(regAddr)

for regAddr in range(0xa3, 0xad):
    read_reg(regAddr)

read_reg(0xb0)
read_reg(0xb1)

read_reg(0xb3)

read_reg(0xb8)

read_reg(0xbb)

read_reg(0xbe)

read_reg(0xcc)

for regAddr in range(0xd0, 0xd9):
    read_reg(regAddr)

read_reg(0xdb)

read_reg(0xe0)
read_reg(0xe1)

read_reg(0xfb)

read_reg(0xff)

for regAddr in extRegList:
    read_reg(regAddr)
