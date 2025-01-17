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
parser.add_argument("--i", type=int, help="shadow register table index in decimal (0-255)")
args = parser.parse_args()


regTblIdx = 0xffff

if args.i is None:
   print("specify shadow register table index (in decimal) to read !!")
   quit()
else:
   regTblIdx = args.i


def Get_Value(Command, command2, ByteCount, tblIdx, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, tblIdx, ByteCount, TIMEOUT_MS)

def read_reg(idx):
    data = Get_Value(0xff, 0x77, 13, idx)
    print(data)
    tblIdx = data[1]
    tblIdx <<= 8
    tblIdx |= data[0]

    errCode = data[2]

    regAddr = data[4]
    regAddr <<= 8
    regAddr |= data[3]

    regReadOpnSts = data[5]
    dataMuxSigLvl = data[6]

    regVal = data[8]
    regVal <<= 8
    regVal |= data[7]

    timeStamp = data[12]
    timeStamp <<= 8
    timeStamp |= data[11]
    timeStamp <<= 8
    timeStamp |= data[10]
    timeStamp <<= 8
    timeStamp |= data[9]

    print("")
    print("Idx: {}, Err: {}, RegAddr: 0x{:02x}, Rd-Sts {}, DATAMUX {}, RegVal: 0x{:04x}, Time-Stamp {}".\
          format(tblIdx, errCode, regAddr, regReadOpnSts, dataMuxSigLvl, regVal, timeStamp))
    # return val      

read_reg(regTblIdx)
