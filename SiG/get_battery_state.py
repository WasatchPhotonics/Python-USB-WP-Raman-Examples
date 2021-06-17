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

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

# 2nd-tier opcode returns three bytes: [LSB, MSB, state]
#
# MSB = integral battery charge level (0-100)
# LSB = fractional battery charge level
#         0 =   0 / 256 = 0.0000%
#       255 = 255 / 256 = 0.9961%
# state = 1 (charging) or 0 (not charging)
#
# E.g., [0x20, 0x40, 0x00] = 64 + 32/256 = 64.125% (not charging)
def get_battery_level():
    raw = Get_Value(0xff, 0x13, 3)
    percentage = raw[1] + (1.0 * raw[0] / 256.0)
    charging = raw[2] != 0
    return (raw, percentage, charging)
    
(raw, percentage, charging) = get_battery_level()
print("Battery Charge Level: %s (%.2f%%) (%s)" % (raw, percentage, "charging" if charging else "not charging"))
