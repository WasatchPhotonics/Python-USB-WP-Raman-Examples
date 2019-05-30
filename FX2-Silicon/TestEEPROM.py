#!/usr/bin/env python -u

import traceback
import usb.core
import argparse
import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
TIMEOUT_MS = 1000
ZZ = [0] * BUFFER_SIZE

MAX_PAGES = 6
PAGE_SIZE = 64

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--pid", default="1000", choices=["1000", "2000", "4000"], help="USB Product ID (hex) (default 1000)")
        self.args = parser.parse_args()

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=int(self.args.pid, 16))
        if not self.dev:
            print("No spectrometers found with PID 0x%s" % self.args.pid)

    def send_cmd(self, cmd, value, index=0, buf=None):
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_buf(self, cmd, value=0, index=0, length=64):
        return self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

    def read_eeprom(self,):
        print("\nReading EEPROM:")
        self.eeprom_pages = []
        for page in range(MAX_PAGES):
            buf = self.get_buf(cmd=0xff, value=0x01, index=page, length=PAGE_SIZE)
            self.eeprom_pages.append(buf)
            print("  Page %d: %s" % (page, buf))

    # for test purposes, only print page 4 (user_text)
    def dump_eeprom(self):
        buf = self.eeprom_pages[4]
        user_text  = ""

        for i in range(len(buf)):
            c = buf[i]
            if c == 0:
                break
            else:
                user_text += chr(c)

        print("\nEEPROM Contents:")
        print("  User Text: [%s]" % user_text)

    def update_buffers(self, user_text):
        length = min(len(user_text), PAGE_SIZE - 1)
        page = 4

        print("\nUpdating buffers")
        print("  user_text -> '%s'" % user_text)
        for i in range(length):
            self.eeprom_pages[page][i] = ord(user_text[i])
        self.eeprom_pages[page][length] = 0

    def write_eeprom(self):
        print("\nWriting EEPROM")
        for page in range(MAX_PAGES - 1, -1, -1):
            DATA_START = 0x3c00
            offset = DATA_START + page * PAGE_SIZE
            if page == 4:
                buf = self.eeprom_pages[page]
                print("  writing page %d, offset 0x%04x: %s" % (page, offset, buf))
                self.send_cmd(0xa2, value=offset, index=0, buf=buf)
            else:
                print("  skipping page %d, offset 0x%04x" % (page, offset))

    def run(self):
        while True:
            try:
                self.read_eeprom()
                self.dump_eeprom()

                new_text = input("\nEnter replacement user_text (Ctrl-C to exit): ")
                self.update_buffers(user_text=new_text)
                self.write_eeprom()
            except KeyboardInterrupt:
                break
            except:
                traceback.print_exc()
                break

fixture = Fixture()
if fixture.dev:
    fixture.run()
