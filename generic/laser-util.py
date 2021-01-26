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
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--enable",              action="store_true", help="fire laser")
        parser.add_argument("--max-sec",             type=int,            help="firing time (sec) (default 1)", default=1)
        parser.add_argument("--mod-enable",          action="store_true", help="enable modulation")
        parser.add_argument("--mod-period-us",       type=int,            help="laser modulation pulse period (us) (default 1000)", default=1000)
        parser.add_argument("--mod-width-us",        type=int,            help="laser modulation pulse width (us) (default 100)", default=100)
        parser.add_argument("--pid",                 default="4000",      help="USB PID in hex (default 4000)", choices=["1000", "2000", "4000"])

        self.args = parser.parse_args()

        # convert PID from hex string
        self.pid = int(self.args.pid, 16)

        # find the FIRST connected spectrometer of the given PID
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):

        # handle disable operation first
        if not self.args.enable:
            self.set_enable(False)
            return

        # apparently we're to fire the laser

        if self.args.mod_enable:
            self.set_modulation_params()

        self.set_enable(True)

        print("sleeping %d sec..." % self.args.max_sec)
        sleep(self.args.max_sec)

        self.set_enable(False)

    ############################################################################
    # opcodes
    ############################################################################

    def set_enable(self, flag):
        print("setting LASER_MOD_ENABLE %s" % ("on" if flag else "off"))
        self.send_cmd(0xbe, 1 if flag else 0)

    def set_modulation_params(self):
        # are modulation parameters valid?
        if self.args.mod_period_us <= self.args.mod_width_us:
            print("disabling modulation (width %d > period %d)" % (self.args.mod_width_us, self.args.mod_period_us))
            self.send_cmd(0xbd, 0)
            return

        (lsb, msb, buf) = self.to40bit(self.args.mod_period_us)
        print("setting LASER_MOD_PULSE_PERIOD %d (lsb %04x, msb %04x, payload %s)" % (self.args.mod_period_us, lsb, msb, buf))
        self.send_cmd(0xc7, value=lsb, index=msb, buf=buf)

        (lsb, msb, buf) = self.to40bit(self.args.mod_width_us)
        print("setting LASER_MOD_PULSE_WIDTH %d (lsb %04x, msb %04x, payload %s)" % (self.args.mod_width_us, lsb, msb, buf))
        self.send_cmd(0xdb, value=lsb, index=msb, buf=buf)

        print("setting LASER_MOD_ENABLE 1")
        self.send_cmd(0xbd, 1)

    ############################################################################
    # Utility Methods
    ############################################################################

    def is_arm(self):
        return self.pid == 0x4000 

    def is_sig(self):
        return self.is_arm() # close enough

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def to40bit(self, val):
        lsb = val & 0xffff
        msb = (val >> 16) & 0xffff
        buf = [ (val >> 32) & 0xff, 0 * 7 ]
        return (lsb, msb, buf)

    def send_cmd(self, cmd, value, index=0, buf=None):
        if buf is None:
            if self.is_arm():
                buf = [0] * 8
            else:
                buf = 0
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64):
        return self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

fixture = Fixture()
if fixture.dev:
    fixture.run()
