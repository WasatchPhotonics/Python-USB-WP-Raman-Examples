#!/usr/bin/env python

import sys
import usb.core

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000
VR_GET_LASER_POWER_ATTENUATION = 0x83

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def get_laser_pwr_attn_level():
    data = Get_Value(VR_GET_LASER_POWER_ATTENUATION, 0x0, 2)
    print("data :", data)
    if data[0] == 0:
       print("laser pwr attn is {}".format(data[1]))
    else:
       print("error code {}".format(data[0]))
       

get_laser_pwr_attn_level()
