#!/usr/bin/env python -u

""" 
This script will switch the ARM microcontroller into "DFU" (Device Firmware Update)
mode, allowing the ARM and FPGA firmware to be updated via USB.

see http://oshgarage.com/dfu-mode-on-a-stm32-microcontroller/

"""

import usb.core

PID = 0x4000

dev = usb.core.find(idVendor=0x24aa, idProduct=PID)
Ret = dev.ctrl_transfer(0x40, 0xFE, 0, 0, [0,0,0,0,0,0,0,0], 1000)
