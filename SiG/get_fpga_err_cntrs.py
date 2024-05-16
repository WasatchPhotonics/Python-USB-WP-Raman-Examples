#!/usr/bin/env python

import sys
import usb.core
from datetime import datetime

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

SC_GET_FPGA_ERR_INTR_COUNTERS = 0x37

FPGA_errIntrErrTypes = \
[ \
  "I2C_WR_ERROR", \
  "I2C_RD_ERROR", \
  "SNSR_STARTUP_TIMEOUT", \
  "SNSR_MESSAGE_VERIFY_ERROR", \
  "SNSR_MESSAGE_OVERFLOW_ERROR", \
  "BIT_SLIP_ERROR1", \
  "BIT_SLIP_ERROR2", \
  "BIT_SLIP_ERROR3", \
  "BIT_SLIP_ERROR4", \
  "BIT_SLIP_ERROR5", \
  "BIT_SLIP_ERROR6", \
  "BIT_SLIP_ERROR7", \
  "BIT_SLIP_ERROR8", \
  "BIT_SLIP_ERROR9", \
  "BIT_SLIP_ERROR10", \
  "BIT_SLIP_ERROR11", \
]

def get_uint(bRequest, wValue, wIndex=0, lsb_len=4):
    # print(f">> ControlPacket(0x{DEVICE_TO_HOST:02x}, bRequest 0x{bRequest:02x}, wValue 0x{wValue:04x}, wIndex 0x{wIndex:04x}, len {lsb_len})")
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
    # print(f"<< {data}")
    value = 0
    for i in range(lsb_len):
        value |= (data[i] << i)
    # print(f"returning 0x{value:04x} ({value})")
    return value

def get_fpga_err_cntrs():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, SC_GET_FPGA_ERR_INTR_COUNTERS, 0, 64, TIMEOUT_MS)
    # print("rcvd resp of len", len(data))
    # print(data)
    shift = 0
    v32 = 0
    retList = []
    for byte in data:
        # print("byte 0x{:x}, shift {}".format(byte, shift))
        tempV32 = byte << shift 
        v32 |= tempV32
        shift += 8
        # print("v32 0x{:x}, shift {}".format(v32, shift))
        if shift > 24:
           shift = 0
           retList.append(v32)
           # print("got counter 0x{:x}".format(v32))
           v32 = 0

    return retList




cntrList = get_fpga_err_cntrs()

idx = 0
for cntr in cntrList:
    print("{} : {}".format(FPGA_errIntrErrTypes[idx], cntr))
    idx += 1


print()
