#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

#import common

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000

FPGA_CONFIG_REQ = 0xB3
FPGA_CONFIG_REG = 0x12
FPGA_CONFIG_READ = 1

buf = [0] * 2

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)

def print_help():
    print("-h : Print help")
    print("arg1 = 0 arg2 = Value(2B) : Write 2 bytes to FPGA Config Register")
    print("arg1 = 1 : Read FPGA Register Value")   

if not dev:
    print("No spectrometers found")
    sys.exit()

if sys.argv[1] == "-h":
    print_help()

elif int(sys.argv[1]) == 1:             # Read 
    result = dev.ctrl_transfer(DEVICE_TO_HOST, FPGA_CONFIG_REQ, 0, 0, buf, TIMEOUT_MS)
    print("FPGA CONFIG REG: 0x%04x" % (result[1] << 8 | result[0]))

elif int(sys.argv[1]) == 0:             # Write
    if sys.argv[2].startswith("0x") or sys.argv[2].startswith("0X"):
        reg_val = int(sys.argv[2], 16)
    else: 
        reg_val = int(sys.argv[2])
    dev.ctrl_transfer(HOST_TO_DEVICE, FPGA_CONFIG_REQ, reg_val, 0, buf, TIMEOUT_MS)
    print("Write to FPGA CONFIG REG: 0x%04x" % reg_val)

else:
    print_help()