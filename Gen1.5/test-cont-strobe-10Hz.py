#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

import common

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if not dev:
    print("No spectrometers found")
    sys.exit()

SET_MOD_PERIOD_US   = 0xc7
GET_MOD_PERIOD_US   = 0xcb
SET_MOD_WIDTH_US    = 0xdb
GET_MOD_WIDTH_US    = 0xdc
SET_MOD_ENABLE      = 0xbd
GET_MOD_ENABLE      = 0xe3
SET_STROBE_ENABLE   = 0xbe

period = 100000
width = 50000

print("Setting Frequency to 10Hz")
common.send_cmd_uint40(dev, SET_MOD_PERIOD_US, period)
common.verify_state(dev, GET_MOD_PERIOD_US, lsb_len=5, expected=period, label="period")

print("setting width to %d us..." % width)
common.send_cmd_uint40(dev, SET_MOD_WIDTH_US, width)
common.verify_state(dev, GET_MOD_WIDTH_US, lsb_len=5, expected=width, label="width")

print("enabling modulation...")
common.send_cmd(dev, SET_STROBE_ENABLE, 1)
common.send_cmd(dev, SET_MOD_ENABLE, 1)
common.verify_state(dev, GET_MOD_ENABLE, msb_len=1, expected=1, label="enable")

print("\r\nPress Enter to end.\r\n")
input()

print("\ndisabling modulation.")
common.send_cmd(dev, SET_STROBE_ENABLE, 0)
common.send_cmd(dev, SET_MOD_ENABLE, 0)
common.verify_state(dev, GET_MOD_ENABLE, msb_len=1, expected=0, label="enable")