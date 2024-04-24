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

def get_value(bRequest, wValue, wIndex=0, lsb_len=4):
    # print(f">> ControlPacket(0x{DEVICE_TO_HOST:02x}, bRequest 0x{bRequest:02x}, wValue 0x{wValue:04x}, wIndex 0x{wIndex:04x}, len {lsb_len})")
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
    # print(f"<< {data}")
    value = 0
    for i in range(lsb_len):
        value |= (data[i] << i)
    # print(f"returning 0x{value:04x} ({value})")
    return value

def get_battery():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x13, 0, 3, TIMEOUT_MS)
    perc = data[1] + (1.0 * data[0] / 256.0)
    charging = 'charging' if data[2] else 'not charging'
    return f"{perc:5.2f}% ({charging})"

# Per Ram:
# 0xff, 0x40 gives you count of keep alive requests sent by STM32 to BLE
# 0xff, 0x41 gives you count of keep alive responses received by STM32 from BLE
# 0xff, 0x38 gives total cnt of messages received by STM32 over the UART link with BLE
# 0xff, 0x39 gives total cnt of messages transmitted by STM32 over the UART link with BLE

print("Timestamp:                  %s" % datetime.now())
print("Battery State:              %s" % get_battery())
print("STM-to-BLE Keepalive Count: %d" % get_value(0xff, 0x40))
print("BLE-to-STM Keepalive Count: %d" % get_value(0xff, 0x41))
print("STM Rx UART Msg Count:      %d" % get_value(0xff, 0x38))
print("STM Tx UART Msg Count:      %d" % get_value(0xff, 0x39))
print()
