#!/usr/bin/env python

import sys
import usb.core

# select product
dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print "No spectrometer found"
    sys.exit()
#print dev

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

# 2nd-tier opcode returns two bytes: [LSB, MSB]
#
# MSB = integral battery charge level (0-100)
# LSB = fractional battery charge level
#         0 =   0 / 256 = 0.0000%
#       255 = 255 / 256 = 0.9961%
#
# E.g., [0x20, 0x40] = 64 + 32/256 = 64.125%
def get_battery_level():
    battery_register = Get_Value(0xff, 0x13, 2)
    battery_charge_level = battery_register[1] + (1.0 * battery_register[0] / 256.0)
    return battery_charge_level
    
print "Battery Charge Level: %.2f" % get_battery_level()
