#!/usr/bin/env python

import sys
import usb.core
import argparse
import time

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
    data = Get_Value(0xff, 0x77, 17, idx)
    # print(data)
    
    snapShotCnt = data[1]
    snapShotCnt <<= 8
    snapShotCnt |= data[0]
    # print("Snapshot Cnt:", snapShotCnt)
    
    regsSavedCnt = data[3]
    regsSavedCnt <<= 8
    regsSavedCnt |= data[2]
    # print("Num Regs Saved:", regsSavedCnt)


    tblIdx = data[5]
    tblIdx <<= 8
    tblIdx |= data[4]

    errCode = data[6]

    regAddr = data[8]
    regAddr <<= 8
    regAddr |= data[7]

    regReadOpnSts = data[9]
    dataMuxSigLvl = data[10]

    regVal = data[12]
    regVal <<= 8
    regVal |= data[11]

    timeStamp = data[16]
    timeStamp <<= 8
    timeStamp |= data[15]
    timeStamp <<= 8
    timeStamp |= data[14]
    timeStamp <<= 8
    timeStamp |= data[13]

    print("")
    print("Idx: {}, RegAddr: 0x{:02x}, Err-Code {}, Rd-Sts {}, DATAMUX {}, RegVal: 0x{:04x}, Time-Stamp {}".\
          format(tblIdx, regAddr, errCode, regReadOpnSts, dataMuxSigLvl, regVal, timeStamp))
    return errCode, snapShotCnt, regsSavedCnt

if regTblIdx < 255:
   err, snapSvdCnt, regSvdCnt = read_reg(regTblIdx)
else:
   regTblIdx = 0
   while 1:
     err, snapSvdCnt, regSvdCnt = read_reg(regTblIdx)
     if err != 0:
        break
     else:
        regTblIdx += 1
        time.sleep(0.1)
 
print("")
print("Snapshot Cnt:", snapSvdCnt)
print("Num Regs Saved:", regSvdCnt)
