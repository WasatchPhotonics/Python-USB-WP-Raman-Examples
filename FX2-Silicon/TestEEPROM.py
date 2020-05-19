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

MAX_PAGES = 8
PAGE_SIZE = 64

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--pid", default="1000", choices=["1000", "2000", "4000"], help="USB Product ID (hex) (default 1000)")
        self.args = parser.parse_args()
        self.pid = int(self.args.pid, 16)

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def send_cmd(self, cmd, value, index=0, buf=None):
        #print("send_cmd: request %02x, cmd %02x, value %04x, index %04x, buf %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_buf(self, cmd, value=0, index=0, length=64):
        print("ctrl_transfer: dir %02x, cmd %04x, value %04x, index %04x, len %02x, timeout %d" % (
            DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS))
        return self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

    def read_eeprom(self):
        print("\nReading EEPROM:")
        self.eeprom_pages = []
        for page in range(MAX_PAGES):
            buf = self.get_buf(cmd=0xff, value=0x01, index=page, length=PAGE_SIZE)
            self.eeprom_pages.append(buf)
            print("  Page %d: %s" % (page, buf))

    def parse_string(self, page, start, length):
        buf = self.eeprom_pages[page]
        s = ""
        for i in range(length):
            c = buf[start + i]
            if c == 0:
                break
            else:
                s += chr(c)
        return s

    def dump_eeprom(self):
        print("\nEEPROM Contents:")
        print("  User Text:             [%s]" % self.parse_string(4,  0, 64))
        print("  Product Configuration: [%s]" % self.parse_string(5, 30, 16))

    def update_string(self, page, start, max_len, value, label):
        print("  %s -> '%s'" % (label, value))
        for i in range(max_len):
            if i < len(value):
                self.eeprom_pages[page][start + i] = ord(value[i])
            else:
                self.eeprom_pages[page][start + i] = 0

    def update_buffers(self, user_text, product_config):
        print("\nUpdating buffers")
        self.update_string(page=4, start=0, max_len=PAGE_SIZE, value=user_text, label="User Text")
        self.update_string(page=5, start=30, max_len=16, value=product_config, label="Product Configuration")

    # believed to work on FX2 and ARM?
    def write_eeprom(self):
        print("\nWriting EEPROM")
        for page in range(MAX_PAGES):
            buf = self.eeprom_pages[page]
            print("  writing page %d: %s" % (page, buf))
            if self.pid == 0x4000:
                self.send_cmd(cmd=0xff, value=0x02, index=page, buf=buf)
            else:
                DATA_START = 0x3c00
                offset = DATA_START + page * 64 
                self.send_cmd(cmd=0xa2, value=offset, index=0, buf=buf)

    def run(self):
        while True:
            try:
                self.read_eeprom()
                self.dump_eeprom()

                new_user_text = input("\nEnter replacement user_text (Ctrl-C to exit): ")
                new_product_config = input("\nEnter product configuration (Ctrl-C to exit): ")
                self.update_buffers(user_text=new_user_text, product_config=new_product_config)
                self.write_eeprom()
            except KeyboardInterrupt:
                break
            except:
                traceback.print_exc()
                break

fixture = Fixture()
if fixture.dev:
    fixture.run()
