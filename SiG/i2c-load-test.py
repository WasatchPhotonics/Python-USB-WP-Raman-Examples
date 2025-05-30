#!/usr/bin/env python

import sys
import random
import datetime
import platform
import usb.core
from time import sleep

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 20000

SIG_LOG_USB_CMD = 0x81
eeprom_pages = []

def get_next_log():
    now = datetime.datetime.now()
    raw = dev.ctrl_transfer(DEVICE_TO_HOST, SIG_LOG_USB_CMD, 0x0, 0, 64, TIMEOUT_MS)
    if len(raw) == 0:
       sleep(1)
       return

    s = ""
    for c in raw[1:]:
        if c == 0:
           break
        s += chr(c)
    if len(s):
        print(f"\n{now}: {s}", end='')
        return True

def get_eeprom_page(page):
    # print(f"reading EEPROM page {page}")
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x01, page, 64, TIMEOUT_MS)
    if data is None or len(data) != 64:
        raise Exception(f"failed to read 64 bytes for EEPROM page {page}")
    return data

def validate_random_eeprom_page():
    page = random.randint(0, 7)
    data = get_eeprom_page(page)
    for i in range(len(data)):
        if data[i] != eeprom_pages[page][i]:
            print(f"\n\nfailed when comparing EEPROM page {page}:")
            print(f"orig: {eeprom_pages[page]}")
            print(f" now: {data}")
            sys.exit(1)
    # print(f"validated EEPROM page {page}")
    print('.', end='')
    sleep(0.05) # 20Hz

# main() #######################################################################

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000, backend=backend.get_backend())
if not dev:
    print("No spectrometer found")
    sys.exit()

# read all pages at start
for i in range(8):
    eeprom_pages.append(get_eeprom_page(i))

while True:
    if not get_next_log():
        validate_random_eeprom_page()
