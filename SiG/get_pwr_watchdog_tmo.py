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
SC_GET_POWER_WATCHDOG_SEC = 0x31

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def get_pwr_watchdog_tmo():
    data = Get_Value(0xff, SC_GET_POWER_WATCHDOG_SEC, 2)
    print("data :", data)
    val = data[1] << 8
    val += data[0]
    return val      

pwrWatchdogTmo = get_pwr_watchdog_tmo() 
print("power watchdog timeout is {} secs".format(pwrWatchdogTmo))
