#!/usr/bin/env python

import sys
import re
from time import sleep

import traceback
import usb.core
import argparse
import struct
import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

MAX_PAGES = 8
PAGE_SIZE = 64
EEPROM_FORMAT = 8

# An extensible, stateful "Test Fixture" 
class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None
        self.subformat = None
        self.dev = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",           action="store_true", help="debug output")
        parser.add_argument("--pid",             default="1000",      help="USB PID in hex (default 1000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--enable",          type=str,            help="dis/enable laser")
        parser.add_argument("--raman-mode",      type=str,            help="dis/enable raman mode (link firing to integration)")
        parser.add_argument("--raman-delay-ms",  type=int,            help="set laser warm-up delay in Raman Mode (~ms)")
        parser.add_argument("--watchdog-sec",    type=int,            help="set laser watchdog (sec)")
        self.args = parser.parse_args()

        # convert PID from hex string
        self.pid = int(self.args.pid, 16)

        # find the FIRST connected spectrometer of the given PID
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        if self.args.watchdog_sec is not None:
            self.set_watchdog_sec(self.args.watchdog_sec)

        if self.args.enable is not None:
            self.set_enable(self.str2bool(self.args.enable))

        if self.args.raman_delay_ms is not None:
            self.set_raman_delay_ms(self.args.raman_delay_ms)

        if self.args.raman_mode is not None:
            self.set_raman_mode(self.str2bool(self.args.raman_mode))

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def set_enable(self, flag):
        print("setting laserEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(0xb3, 1 if flag else 0)

    def set_raman_mode(self, flag):
        print("setting Raman Mode %s" % ("on" if flag else "off"))
        self.send_cmd(0xff, 0x16, 1 if flag else 0)

    def set_raman_delay_ms(self, ms):
        if ms < 0 or ms > 0xffff:
            print("ERROR: raman delay requires uint16")
            return

        print("setting Raman Delay %d ms" % ms)
        self.send_cmd(0xff, 0x20, ms)

    def set_watchdog_sec(self, sec):
        if sec < 0 or sec > 0xffff:
            print("ERROR: watchdog requires uint16")
            return

        print("setting Raman Watchdog %d sec" % sec)
        self.send_cmd(0xff, 0x18, sec)

    ############################################################################
    # Utility Methods
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value, index=0, buf=None):
        if buf is None:
            if self.pid == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(%02x, %02x, %04x, %04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64):
        return self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

fixture = Fixture()
if fixture.dev:
    fixture.run()
