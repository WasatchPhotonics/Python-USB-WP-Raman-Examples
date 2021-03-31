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

SET_MOD_LINKED_TO_INTEGRATION = 0xdd
GET_MOD_LINKED_TO_INTEGRATION = 0xde

SET_INTEGRATION_TIME = 0xb2
GET_INTEGRATION_TIME = 0xbf

SET_TRIGGER_SOURCE = 0xd2
GET_TRIGGER_SOURCE = 0xd3

SET_MOD_PULSE_DELAY = 0xc6
GET_MOD_PULSE_DELAY = 0xca

integration_time = 10000    #us
period = 1000               #us
width = 500                 #us

print("\r\nSetting Trigger Source: External")
common.send_cmd_uint40(dev, SET_TRIGGER_SOURCE, 1)
common.verify_state(dev, GET_TRIGGER_SOURCE, msb_len=1, expected=1, label="enable")

print("\r\nLinking Modulation to Integration")
common.send_cmd_uint40(dev, SET_MOD_LINKED_TO_INTEGRATION, 1)
common.verify_state(dev, GET_MOD_LINKED_TO_INTEGRATION, msb_len=1, expected=1, label="enable")

print("\r\nSetting Integration Time: 10ms")
common.send_cmd_uint40(dev, SET_INTEGRATION_TIME, integration_time)
common.verify_state(dev, GET_INTEGRATION_TIME, lsb_len=5, expected=integration_time, label="integration time")

print("\r\nSetting Frequency to 1KHz")
common.send_cmd_uint40(dev, SET_MOD_PERIOD_US, period)
common.verify_state(dev, GET_MOD_PERIOD_US, lsb_len=5, expected=period, label="period")

print("\r\nsetting width to %d us..." % width)
common.send_cmd_uint40(dev, SET_MOD_WIDTH_US, width)
common.verify_state(dev, GET_MOD_WIDTH_US, lsb_len=5, expected=width, label="width")

print("\r\nenabling modulation...")
common.send_cmd(dev, SET_STROBE_ENABLE, 1)
common.send_cmd(dev, SET_MOD_ENABLE, 1)
common.verify_state(dev, GET_MOD_ENABLE, msb_len=1, expected=1, label="enable")

print("\r\nReady for External Trigger.\r\n")
input("Press Enter to end")

print("\ndisabling modulation.")
common.send_cmd_uint40(dev, SET_TRIGGER_SOURCE, 0)
common.send_cmd_uint40(dev, SET_MOD_LINKED_TO_INTEGRATION, 0)
common.send_cmd(dev, SET_STROBE_ENABLE, 0)
common.send_cmd(dev, SET_MOD_ENABLE, 0)
common.verify_state(dev, GET_MOD_ENABLE, msb_len=1, expected=0, label="enable")