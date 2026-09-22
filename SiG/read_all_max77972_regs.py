#!/usr/bin/env python

import sys
import argparse
import usb.core
import platform

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--short", action="store_true", help="reduced list of registers")
args = parser.parse_args()

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000, backend=backend.get_backend())

if not dev:
   print("No spectrometer found")
   sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

regAddr = 0xffff

def Get_Cmd(cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None):
    result = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
    value = 0
    if msb_len is not None:
        for i in range(msb_len):
            value = value << 8 | result[i]
        return value
    elif lsb_len is not None:
        for i in range(lsb_len):
            value = (result[i] << (8 * i)) | value
        return value
    else:
        return result

def Get_Value(Command, command2, ByteCount, regAddr, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, regAddr, 3, TIMEOUT_MS)

def read_reg(regAddr):
    if args.short and regAddr not in [ 0x002f ]:
        return

    data = Get_Value(0xff, 0x76, 3, regAddr)
    val = 0
    if data[0] != 0:
       print("Flr !! rc", data[0])
    else:
       val = data[2]
       val <<= 8
       val |= data[1]
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
    0x02,
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

result = Get_Cmd(0xc0)
if result is not None and len(result) >= 4:
    print("Firmware %d.%d.%d.%d" % (result[3], result[2], result[1], result[0]))

for regAddr in range(83):
    if regAddr in skipList:
       continue
    read_reg(regAddr)

for regAddr in range(128, 160):
    read_reg(regAddr)

for regAddr in range(0xa3, 0xad):
    read_reg(regAddr)

for regAddr in [ 0xb0, 0xb1, 0xb3, 0xb8, 0xbb, 0xbe, 0xcc ]:
    read_reg(regAddr)

for regAddr in range(0xd0, 0xd9):
    read_reg(regAddr)

for readAddr in [ 0xdb, 0xe0, 0xe1, 0xff ]:
    read_reg(regAddr)

for regAddr in extRegList:
    read_reg(regAddr)
