#!/usr/bin/env python

import os
import sys

from time import sleep
from datetime import datetime

import usb.core
import platform
import argparse
import sys

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

class Fixture:

    def __init__(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug", action="store_true", help="debug output")
        parser.add_argument("--time-sec", type=int, default=0, help="how long to fire laser")
        self.args = parser.parse_args()

        self.dev = None
        for pid in [0x4000, 0x1000, 0x2000]:
            if self.dev is None:
                for dev in usb.core.find(find_all=True, idVendor=0x24aa, idProduct=pid, backend=backend.get_backend()):
                    self.dev = dev
                    break

        if not self.dev:
            print("No spectrometers found.")
            sys.exit(1)

    def run(self):
        if self.args.time_sec < 1:
            return

        print("Firing laser...")
        self.set_laser_enable(True)

        print(f"Waiting {self.args.time_sec}sec", end='')
        for _ in range(self.args.time_sec):
            print(".", end='')
            sleep(1)
        print("")

        print("Disabling laser.")
        self.set_laser_enable(False)

    def set_laser_enable(self, flag):
        self.send_cmd(0xbe, 1 if flag else 0)

    def debug(self, msg):
        if self.args.debug:
            print(f"DEBUG: {msg}")

    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            if self.dev.idProduct == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None):
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, label))
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) << %s %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, self.to_hex(result), label))

        value = 0
        if msb_len is not None:
            for i in range(msb_len):
                value = value << 8 | result[i]
            return value
        elif lsb_len is not None:
            for i in range(lsb_len):
                value = (result[i] << (8 * i)) | value
            return value
        else:
            return result

fixture = Fixture()
fixture.run()
