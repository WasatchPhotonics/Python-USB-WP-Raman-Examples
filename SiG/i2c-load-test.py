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

class Fixture:

    def __init__(self):
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000, backend=backend.get_backend())
        if not self.dev:
            print("No spectrometer found")
            sys.exit()

        self.eeprom_pages = []
        self.page_reads = 0
        self.needs_lf = False

        for i in range(8):
            self.eeprom_pages.append(self.get_eeprom_page(i))

    def get_next_log(self):
        now = datetime.datetime.now()
        raw = self.dev.ctrl_transfer(DEVICE_TO_HOST, SIG_LOG_USB_CMD, 0x0, 0, 64, TIMEOUT_MS)
        if len(raw) == 0:
           sleep(1)
           return

        s = ""
        for c in raw[1:]:
            if c == 0:
               break
            s += chr(c)
        if s == "":
            return

        if self.needs_lf:
            print("")
            self.needs_lf = False
        print(f"{now}: {s}")
        return True

    def get_eeprom_page(self, page):
        data = self.dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x01, page, 64, TIMEOUT_MS)
        if data is None or len(data) != 64:
            raise Exception(f"failed to read 64 bytes for EEPROM page {page}")
        self.page_reads += 1
        return data

    def validate_random_eeprom_page(self):
        page = random.randint(0, 7)
        data = self.get_eeprom_page(page)
        for i in range(len(data)):
            if data[i] != self.eeprom_pages[page][i]:
                print(f"\n\nfailed when comparing EEPROM page {page}:")
                print(f"orig: {eeprom_pages[page]}")
                print(f" now: {data}")
                sys.exit(1)
        print(f"\rValidated EEPROM page {page} | Total page reads {self.page_reads}", end='')
        self.needs_lf = True
        sleep(0.05) # 20Hz

    def run(self):
        while True:
            if not self.get_next_log():
                self.validate_random_eeprom_page()

# main() 
fixture = Fixture()
fixture.run()
