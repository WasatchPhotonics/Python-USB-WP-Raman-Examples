#!/usr/bin/env python

import sys
import re
from time import sleep
from datetime import datetime

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

        parser = argparse.ArgumentParser(
            description="Command-line utility to play with lasers (INHERENTLY DANGEROUS!)",
            epilog="To manually turn the laser off after an arbitrary delay, use --max-ms 0. " +
                   "To exit the script with laser still firing (HIGHLY DANGEROUS), use --max-ms -1."
        )
        parser.add_argument("--pid",                    default="4000",      help="USB PID in hex (default 4000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--debug",                  action="store_true", help="debug output")
        parser.add_argument("--enable",                 action="store_true", help="fire laser")
        parser.add_argument("--max-ms",                 type=int,            help="firing time (ms) (default 1000)", default=1000)
        parser.add_argument("--mod-enable",             action="store_true", help="enable modulation")
        parser.add_argument("--mod-period-us",          type=int,            help="laser modulation pulse period (us) (default 1000)", default=1000)
        parser.add_argument("--mod-width-us",           type=int,            help="laser modulation pulse width (us) (default 100)", default=100)
        parser.add_argument("--sig-laser-tec-setpoint", type=int,            help="12-bit SiG laser TEC setpoint (default 0)", default=0)
        parser.add_argument("--sig-laser-ramp-tec",     action="store_true", help="ramp SiG TEC setpoint min->max->min")
        parser.add_argument("--sig-laser-ramp-tec-step",type=int,            help="ramp increment (default 200)", default=200)
        parser.add_argument("--sig-laser-ramp-tec-max", type=int,            help="ramp increment (default 200)", default=4095)
        parser.add_argument("--sig-laser-ramp-tec-min", type=int,            help="ramp increment (default 200)", default=0)

        self.args = parser.parse_args()

        # convert PID from hex string
        self.pid = int(self.args.pid, 16)

        # find the FIRST connected spectrometer of the given PID
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):

        if self.args.sig_laser_tec_setpoint > 0:
            self.set_sig_laser_tec_setpoint(self.args.sig_laser_tec_setpoint)

        # handle disable operation first
        if not self.args.enable:
            self.set_enable(False)
            return

        # apparently we're to fire the laser

        if self.args.mod_enable:
            self.set_modulation_params()
        else:
            self.set_modulation_enable(False)

        self.set_enable(True)

        if self.args.sig_laser_ramp_tec:
            self.do_laser_tec_ramp()
        else:
            if self.args.max_ms > 0:
                self.sleep_ms(self.args.max_ms)
            elif self.args.max_ms == 0:
                cont = input("\nPress <enter> to disable laser...")
            elif self.args.max_ms == -1:
                print("DANGER -- Exiting with laser still firing!!!")
                sys.exit(1)

        self.set_enable(False)

    def do_laser_tec_ramp(self):
        lo = self.args.sig_laser_ramp_tec_min
        hi = self.args.sig_laser_ramp_tec_max
        step = self.args.sig_laser_ramp_tec_step

        for dac in range(lo, hi+1, step):
            self.set_sig_laser_tec_setpoint(dac)
            self.sleep_ms(self.args.max_ms)

        for dac in range(hi, lo-1, -1 * step):
            self.set_sig_laser_tec_setpoint(dac)
            self.sleep_ms(self.args.max_ms)
            
    def sleep_ms(self, ms):
        print(f"sleeping {ms} ms...")
        if ms > 1000 and self.pid == 0x4000:
            # monitor battery while sleeping
            start = datetime.now()
            while (datetime.now() - start).total_seconds() * 1000.0 < ms:
                print("Battery: " + self.get_battery_level())
                sleep(1)
        else:
            sleep(ms/1000.0)

    ############################################################################
    # opcodes
    ############################################################################

    def get_battery_level(self):
        raw = self.get_cmd(0xff, 0x13, 3)
        percentage = raw[1] + (1.0 * raw[0] / 256.0)
        charging = raw[2] != 0
        return f"%s (%.2f%%) (%s)" % (raw, percentage, "charging" if charging else "not charging")

    def set_enable(self, flag):
        print("setting LASER_ENABLE %s" % ("on" if flag else "off"))
        self.send_cmd(0xbe, 1 if flag else 0)

    def set_sig_laser_tec_setpoint(self, dac):
        print(f"setting LASER_TEC_SETPOINT 0x{dac:02x}")
        self.send_cmd(0xa6, dac)

    def set_modulation_enable(self, flag):
        print("setting LASER_MOD_ENABLE %s" % ("on" if flag else "off"))
        self.send_cmd(0xbd, 1 if flag else 0)

    def set_modulation_params(self):
        if self.args.mod_period_us > 0xffff or \
           self.args.mod_width_us > 0xffff:
            print("error: lame script doesn't support full 40-bit 5-byte args")
            return

        # should we modulate after all?
        if self.args.mod_period_us <= self.args.mod_width_us:
            print("disabling modulation because period %d <= width %d" % (self.args.mod_period_us, self.args.mod_width_us))
            self.set_modulation_enable(False)
            return

        print("setting LASER_MOD_PULSE_PERIOD %d" % self.args.mod_period_us)
        self.send_cmd(0xc7, self.args.mod_period_us, buf=[0]*8)

        print("setting LASER_MOD_PULSE_WIDTH %d" % self.args.mod_width_us)
        self.send_cmd(0xdb, self.args.mod_width_us, buf=[0]*8)

        self.set_modulation_enable(True)

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
