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
        parser.add_argument("--acquire-after",       action="store_true", help="acquire after")
        parser.add_argument("--acquire-before",      action="store_true", help="acquire before")
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--enable",              type=str,            help="dis/enable laser (bool)", default="off")
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms)")
        parser.add_argument("--mod-enable",          type=str,            help="dis/enable laser modulation")
        parser.add_argument("--pid",                 default="4000",      help="USB PID in hex (default 4000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--raman-delay-ms",      type=int,            help="set laser warm-up delay in Raman Mode (~ms)")
        parser.add_argument("--raman-mode",          type=str,            help="dis/enable raman mode (links firing to integration) (bool)")
        parser.add_argument("--selected-adc",        type=int,            help="set selected adc")
        parser.add_argument("--selected-laser",      type=int,            help="set selected laser")
        parser.add_argument("--startline",           type=int,            help="set startline for binning")
        parser.add_argument("--stopline",            type=int,            help="set stopline for binning")
        parser.add_argument("--watchdog-sec",        type=int,            help="set laser watchdog (sec)")

        self.args = parser.parse_args()

        # convert PID from hex string
        self.pid = int(self.args.pid, 16)

        # find the FIRST connected spectrometer of the given PID
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        if self.args.acquire_before:
            self.acquire()
            
        if self.args.mod_enable is not None:
            self.set_modulation_enable(self.str2bool(self.args.mod_enable))

        if self.args.watchdog_sec is not None:
            self.set_watchdog_sec(self.args.watchdog_sec)

        if self.args.integration_time_ms is not None:
            self.set_integration_time_ms(self.args.integration_time_ms)

        if self.args.selected_adc is not None:
            self.set_selected_adc(self.args.selected_adc)

        if self.args.selected_laser is not None:
            self.set_selected_laser(self.args.selected_laser)

        if self.args.raman_delay_ms is not None:
            self.set_raman_delay_ms(self.args.raman_delay_ms)

        if self.args.raman_mode is not None:
            self.set_raman_mode(self.str2bool(self.args.raman_mode))
			
        if self.args.enable is not None:
            self.set_enable(self.str2bool(self.args.enable))

        if self.args.startline is not None:
            self.set_startline(self.args.startline)
            self.get_startline()

        if self.args.stopline is not None:
            self.set_stopline(self.args.stopline)			

        if self.args.acquire_after:
            self.acquire()

    ############################################################################
    # opcodes
    ############################################################################

    def set_enable(self, flag):
        print("setting laserEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(0xbe, 1 if flag else 0)

    def set_selected_laser(self, n):
        if n < 0 or n > 0xffff:
            print("ERROR: selectedLaser requires uint16")
            return

        print("setting selectedLaser to %d" % n)
        self.send_cmd(0xff, 0x15, n)

    def set_selected_adc(self, n):
        if not n in (0, 1):
            print("ERROR: selectedADC requires 0 or 1")
            return

        print("setting selectedADC to %d" % n)
        self.send_cmd(0xed, n)

    def set_integration_time_ms(self, n):
        if n < 1 or n > 0xffff:
            print("ERROR: integrationTimeMS requires positive uint16")
            return

        print("setting integrationTimeMS to %d" % n)
        self.send_cmd(0xb2, n)

    def set_modulation_enable(self, flag):
        print("setting laserModulationEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(0xbd, 1 if flag else 0)

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

    def acquire(self):
        print("performing acquire")
        self.send_cmd(0xad, 1)
		
    def set_startline(self, linenum):
        if linenum < 0 or linenum > 0x0436:
            print("ERROR: choose a line between 0 and 1078")
            return

        print("setting startline to %d" % linenum)
        self.send_cmd(0xff, 0x21, linenum)	

    def set_stopline(self, linenum):
        if linenum < 2 or linenum > 0x0438:
            print("ERROR: choose a line between 2 and 1080")
            return

        print("setting stopline to %d" % linenum)
        self.send_cmd(0xff, 0x23, linenum)	

    def get_startline(self):
        data = self.get_cmd(0xff, 0x22)
        print(data)		
        print("The Startline is %d" % (data[0] + data[1]*256))


    ############################################################################
    # Utility Methods
    ############################################################################

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value, index=0, buf=None):
        if buf is None:
            if self.pid == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64):
        return self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

fixture = Fixture()
if fixture.dev:
    fixture.run()