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
VR_SET_LASER_POWER_ATTENUATION = 0x82


parser = argparse.ArgumentParser()
parser.add_argument("--attn", type=int, help="attenuation setpoint (0 to 255)")
args = parser.parse_args()

attnSetPoint = -1

if args.attn is None:
   print("specify attn setpoint (0 to 255) !!")
   quit()

if args.attn is not None:
   attnSetPoint = args.attn
   # print("attn setpoint ", attnSetPoint)
   if attnSetPoint < 0 or attnSetPoint > 255:
      print("attn setpoint range is 0 to 255 !!")
      quit()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def set_laser_pwr_attn_level(setPoint):
    # send_cmd(VR_SET_LASER_POWER_ATTENUATION, setPoint)
    cmd = VR_SET_LASER_POWER_ATTENUATION
    value = setPoint
    index = 0
    length = 1
    resp = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
    print("resp is ", resp)
    if resp[0] == 0:
       print("laser pwr attn set to {}".format(setPoint))
    else:
       print("failed to set laser pwr attn - error code {}".format(resp[0]))
       

set_laser_pwr_attn_level(attnSetPoint)
# print("sent setpoint {} to unit".format(attnSetPoint))
