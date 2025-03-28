#!/usr/bin/env python -u

import sys
import usb.core
import datetime
from time import sleep

dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def Get_Raw(Command, ByteCount=64, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, TIMEOUT_MS)

def Get_Raw_2(Command, Command2, ByteCount=64, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, Command2, 0, ByteCount, TIMEOUT_MS)

def Get_Value(Command, ByteCount, index=0):
    try:
        RetVal = 0
        RetArray = Get_Raw(Command, ByteCount, index)
        for i in range (0, ByteCount):
            RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
        return (RetVal, RetArray)
    except:
        return ("error", "error")


def Get_Value_2(Command, Command2, ByteCount, index=0):
    try:
        RetVal = 0
        RetArray = Get_Raw_2(Command, Command2, ByteCount, index)
        for i in range (0, ByteCount):
            RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
        return (RetVal, RetArray)
    except:
        return ("error", "error")

def Get_Val_u16(opCode, str):
  data = Get_Raw_2(0xff, opCode)
  cnt = data[1]
  cnt <<= 8
  cnt |= data[0]
  print(str, "Val:", cnt)


def Get_Val_u16_1(opCode, str):
  data = Get_Raw(opCode, ByteCount=2)
  val = data[1]
  val <<= 8
  val |= data[0]
  print(str, "Val:", val)
  

data = Get_Raw_2(0xff, 0x30)
ep2IntCnt = data[1]
ep2IntCnt <<= 8
ep2IntCnt  |= data[0]
print("EP2 Int Cnt:", ep2IntCnt)

data = Get_Raw_2(0xff, 0x31)
ep6IntCnt = data[1]
ep6IntCnt <<= 8
ep6IntCnt  |= data[0]
print("EP6 Int Cnt:", ep6IntCnt)

Get_Val_u16(0x35, "Area Scan Started")
Get_Val_u16(0x34, "Area Scan Done")
Get_Val_u16(0x37, "Area Scan trigg")
Get_Val_u16(0x36, "Area Scan tot trigg")

Get_Val_u16_1(0xa5, "Area Scan Line Cnt")

Get_Val_u16_1(0xa7, "Area Scan Line Intv")


data = Get_Raw(0xfa)
FPGA_cfg_shadow_reg = data[1]
FPGA_cfg_shadow_reg <<= 8
FPGA_cfg_shadow_reg |= data[0]
print("FPGA Cfg Reg Shadow : 0x{:04x}".format(FPGA_cfg_shadow_reg))
print("USB HS Cap         %8s %s" % Get_Value_2(0xff, 0x20, 1))
print("LASER Avail        %8s %s" % Get_Value_2(0xff, 0x22, 1))
print("LASER On/Off       %8s %s" % Get_Value(0xe2, 1))
print("CCD Temp SP        %8s %s" % Get_Value(0xd9, 2))
print("Integration Time   %8s %s" % Get_Value(0xbf, 6))
print("CCD Offset         %8s %s" % Get_Value(0xc4, 2))
print("CCD Gain           %8s %s" % Get_Value(0xc5, 2))
print("CCD Temp ENABLE    %8s %s" % Get_Value(0xda, 1))
print("Laser Mod Duration %8s %s" % Get_Value(0xc3, 5))
print("Laser Mod Delay    %8s %s" % Get_Value(0xca, 5))
print("Laser Mod Period   %8s %s" % Get_Value(0xcb, 5))
print("Laser Diode Temp   %8s %s" % Get_Value(0xd5, 2))
print("Actual Int Time    %8s %s" % Get_Value(0xdf, 6))
print("CCD Temperature    %8s %s" % Get_Value(0xd7, 2))
print("Interlock          %8s %s" % Get_Value(0xef, 1))
print("uC FW Version      %s"     % ".".join(str(x) for x in list(reversed(list(Get_Raw(0xc0))))))
print("FPGA FW Version    %s"     % "".join(chr(c) for c in Get_Raw(0xb4)))
