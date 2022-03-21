#!/usr/bin/env python -u

import usb.core

dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
# print(dev)

HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xc0
TIMEOUT_MS      = 1000

CAN_LASER_FIRE  = 0xef
IS_LASER_FIRING = 0xff          # Note this is a secondary command call, the opcode is 0x0d which is included as the default value for param wValue in the getValue fuction def below

def getValue(bRequest, wValue=0x0d, wIndex=0, len_lsb=1):
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, len_lsb, TIMEOUT_MS)
    datalen = len(data)
    # convert response array to uint in LSB order
    result = 0
    for i in range(datalen):
        result = (result << 8) | data[datalen - i - 1]
    return result 

print(f"CAN_LASER_FIRE  (0x{CAN_LASER_FIRE:02x}): {getValue(CAN_LASER_FIRE)}")
print(f"IS_LASER_FIRING (0x{IS_LASER_FIRING:02x}): {getValue(IS_LASER_FIRING)}")
