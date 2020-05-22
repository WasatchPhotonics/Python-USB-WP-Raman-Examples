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
        parser.add_argument("--startline",           type=int,            help="set startline for binning (not laser but hey)")
        parser.add_argument("--stopline",            type=int,            help="set stopline for binning (not laser)")
        parser.add_argument("--watchdog-sec",        type=int,            help="set laser watchdog (sec)")

        self.args = parser.parse_args()

        # convert PID from hex string
        self.pid = int(self.args.pid, 16)

        # find the FIRST connected spectrometer of the given PID
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        self.dump("before")

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

        if self.args.raman_delay_ms is not None:
            self.set_raman_delay_ms(self.args.raman_delay_ms)

        if self.args.raman_mode is not None:
            self.set_raman_mode(self.str2bool(self.args.raman_mode))
			
        if self.args.enable is not None:
            self.set_enable(self.str2bool(self.args.enable))

        if self.args.startline is not None:
            self.set_startline(self.args.startline)

        if self.args.stopline is not None:
            self.set_stopline(self.args.stopline)			

        if self.args.acquire_after:
            self.acquire()

        self.dump("after")

    ############################################################################
    # opcodes
    ############################################################################

    ### Acquire ###############################################################

    def acquire(self):
        print("performing acquire")
        self.send_cmd(0xad, 1)

    ### Enabled ###############################################################
		
    def get_enable(self):
        return 0 != self.get_cmd(0xe2)[0]

    def set_enable(self, flag):
        print("setting laserEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(0xbe, 1 if flag else 0)

    ### Selected ADC ##########################################################

    def get_selected_adc(self):
        return self.get_cmd(0xee)[0]

    def set_selected_adc(self, n):
        if not n in (0, 1):
            print("ERROR: selectedADC requires 0 or 1")
            return

        print("setting selectedADC to %d" % n)
        self.send_cmd(0xed, n)

    ### Integration Time ######################################################

    def get_integration_time_ms(self):
        data = self.get_cmd(0xbf)
        return data[0] + (data[1] << 8) + (data[2] << 16)

    def set_integration_time_ms(self, n):
        # don't worry about 24-bit values
        if n < 1 or n > 0xffff:
            print("ERROR: integrationTimeMS requires positive uint16")
            return

        print("setting integrationTimeMS to %d" % n)
        self.send_cmd(0xb2, n)

    ### Modulation Enable #####################################################

    def get_modulation_enable(self):
        return self.get_cmd(0xe3)[0]

    def set_modulation_enable(self, flag):
        print("setting laserModulationEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(0xbd, 1 if flag else 0)

    ### Raman Mode ############################################################

    def get_raman_mode(self):
        if not self.is_sig():
            return
        return self.get_cmd(0xff, 0x15)[0]

    def set_raman_mode(self, flag):
        if not self.is_sig():
            return
        print("setting Raman Mode %s" % ("on" if flag else "off"))
        self.send_cmd(0xff, 0x16, 1 if flag else 0)

    ### Raman Delay ###########################################################

    def get_raman_delay_ms(self):
        if not self.is_sig():
            return
        return self.get_cmd(0xff, 0x19)[0]

    def set_raman_delay_ms(self, ms):
        if not self.is_sig():
            return
        if ms < 0 or ms > 0xffff:
            print("ERROR: raman delay requires uint16")
            return

        print("setting Raman Delay %d ms" % ms)
        self.send_cmd(0xff, 0x20, ms)

    ### Watchdog ###############################################################

    def get_watchdog_sec(self):
        if not self.is_sig():
            return
        return get_cmd(0xff, 0x17)

    def set_watchdog_sec(self, sec):
        if not self.is_sig():
            return
        if sec < 0 or sec > 0xffff:
            print("ERROR: watchdog requires uint16")
            return

        print("setting Raman Watchdog %d sec" % sec)
        self.send_cmd(0xff, 0x18, sec)

    ### Start Line #############################################################

    def get_startline(self):
        if not self.is_sig():
            return
        data = self.get_cmd(0xff, 0x22)
        return data[0] + (data[1] << 8)

    def set_startline(self, linenum):
        if not self.is_sig():
            return
        if linenum < 0 or linenum > 0x0436:
            print("ERROR: choose a line between 0 and 1078")
            return

        print("setting startline to %d" % linenum)
        self.send_cmd(0xff, 0x21, linenum)	

    ### Stop Line ##############################################################

    def get_stopline(self):
        if not self.is_sig():
            return
        data = self.get_cmd(0xff, 0x24)
        return data[0] + (data[1] << 8)

    def set_stopline(self, linenum):
        if not self.is_sig():
            return
        if linenum < 2 or linenum > 0x0438:
            print("ERROR: choose a line between 2 and 1080")
            return

        print("setting stopline to %d" % linenum)
        self.send_cmd(0xff, 0x23, linenum)	

    def dump(self, label):
        print("%s:" % label)
        print("    Laser enabled:       %s" % self.get_enable())
        print("    Selected ADC:        %s" % self.get_selected_adc())
        print("    Integration Time ms: %s" % self.get_integration_time_ms())
        print("    Modulation enabled:  %s" % self.get_modulation_enable())
        print("    Raman Mode:          %s" % self.get_raman_mode())
        print("    Raman Delay ms:      %s" % self.get_raman_delay_ms())
        print("    Start line:          %s" % self.get_startline())
        print("    Stop line:           %s" % self.get_stopline())

    ############################################################################
    # Utility Methods
    ############################################################################

    def is_sig(self):
        return self.pid == "4000" # close enough for now

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
