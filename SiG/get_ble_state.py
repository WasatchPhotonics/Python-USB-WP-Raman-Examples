#!/usr/bin/env python

import sys
import usb.core
import platform
from datetime import datetime

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000, backend=backend.get_backend())

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def get_uint(bRequest, wValue, wIndex=0, lsb_len=4):
    try:
        # print(f">> ControlPacket(0x{DEVICE_TO_HOST:02x}, bRequest 0x{bRequest:02x}, wValue 0x{wValue:04x}, wIndex 0x{wIndex:04x}, len {lsb_len})")
        data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, lsb_len, TIMEOUT_MS)
        # print(f"<< {data}")
        value = 0
        for i in range(len(data)):
            value |= (data[i] << (8 * i))
        # print(f"returning 0x{value:04x} ({value})")
        return value
    except:
        return f"get_uint failed on bRequest 0x{bRequest:02x}, wValue 0x{wValue:02x}"

def get_string(bRequest, wValue, wIndex=0, length=32):
    data = dev.ctrl_transfer(DEVICE_TO_HOST, bRequest, wValue, wIndex, length, TIMEOUT_MS)
    s = ""
    for c in data:
        if c == 0:
            break
        s += chr(c)
    return s

def get_battery():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x13, 0, 3, TIMEOUT_MS)
    perc = data[1] + (1.0 * data[0] / 256.0)
    charging = 'charging' if data[2] else 'not charging'
    return f"{perc:5.2f}% ({charging})"

def get_firmware_version():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xc0, 0, 0, 8, TIMEOUT_MS)
    return ".".join([str(d) for d in reversed(data)])

def get_fpga_version():
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xb4, 0, 0, 1, TIMEOUT_MS)
    print(data)
    #data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xea, 0, 0, 7, TIMEOUT_MS)
    #data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xe9, 0, 0, 7, TIMEOUT_MS)
    return "".join([chr(c) for c in data])

#data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xf8, 0, 0, 1, TIMEOUT_MS)
#print("FX2 EEPROM I2C Addr:", data)

#data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xf9, 0, 0, 1, TIMEOUT_MS)
#print("FX2 EEPROM Dual Byte Addr Support:", data)

print(get_fpga_version())



quit()
