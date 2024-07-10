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
TIMEOUT_MS = 5000

MAX_PAGES = 8
PAGE_SIZE = 64

# An extensible, stateful "Test Fixture" 
class Fixture(object):
    def __init__(self):
        self.dev = None

        parser = argparse.ArgumentParser(
            description="Command-line utility to play with lasers (INHERENTLY DANGEROUS!)",
            epilog="To manually turn the laser off after an arbitrary delay, use --max-ms 0. " +
                   "To exit the script with laser still firing (HIGHLY DANGEROUS), use --max-ms -1."
        )
        parser.add_argument("--pid",                    default="4000",      help="USB PID in hex (default 4000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--debug",                  action="store_true", help="debug output")
        parser.add_argument("--enable",                 action="store_true", help="fire laser")
        parser.add_argument("--watchdog-sec",           type=int,            help="laser watchdog (seconds)")
        parser.add_argument("--laser-warning-sec",      type=int,            help="laser warning delay (seconds)")
        parser.add_argument("--max-ms",                 type=int,            help="firing time (ms) (default 1000)", default=1000)
        parser.add_argument("--mod-enable",             action="store_true", help="enable modulation")
        parser.add_argument("--mod-period-us",          type=int,            help="laser modulation pulse period (us) (default 1000)", default=1000)
        parser.add_argument("--mod-width-us",           type=int,            help="laser modulation pulse width (us) (default 100)", default=100)
        parser.add_argument("--monitor-laser-state",    action="store_true", help="monitor LASER_CAN_FIRE and LASER_IS_FIRING")
        parser.add_argument("--ramp",                   action="store_true", help="ramp PWM up and down")

        self.args = parser.parse_args()

        # convert PID from hex string
        self.pid = int(self.args.pid, 16)

        # find the FIRST connected spectrometer of the given PID
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):

        print("Battery: " + self.get_battery_level())

        # handle disable operation first
        if not self.args.enable:
            self.set_enable(False)
            return

        if self.args.watchdog_sec is not None:
            self.set_laser_watchdog(self.args.watchdog_sec)

        # apparently we're to fire the laser

        if self.args.mod_enable:
            self.set_modulation_params()
        else:
            self.set_modulation_enable(False)

        if self.args.laser_warning_sec is not None:
            self.set_laser_warning_delay_sec(self.args.laser_warning_sec)

        self.set_enable(True)

        if self.args.ramp:
            self.do_ramp()

        if self.args.max_ms > 0:
            self.sleep_ms(self.args.max_ms)
        elif self.args.max_ms == 0:
            cont = input("\nPress <enter> to disable laser...")
        elif self.args.max_ms == -1:
            print("DANGER -- Exiting with laser still firing!!!")
            sys.exit(1)

        self.set_enable(False)

    def sleep_ms(self, ms):
        print(f"sleeping {ms} ms...")
        if ms > 1000 and self.pid == 0x4000:
            # monitor battery while sleeping
            start = datetime.now()
            while (datetime.now() - start).total_seconds() * 1000.0 < ms:
                print("Battery: " + self.get_battery_level())
                if self.args.monitor_laser_state:
                    print(f"Laser Can Fire: {self.get_laser_can_fire()}")
                    print(f"Laser Is Firing: {self.get_laser_is_firing()}")
                sleep(1)
        else:
            sleep(ms/1000.0)

    def do_ramp(self):
        for width_us in [ 900, 500, 200, 500, 900 ]:
            self.set_modulation_params(period_us=1000, width_us=width_us)
            if self.args.max_ms > 0:
                self.sleep_ms(self.args.max_ms)
            else:
                input("Press return to advance ramp")

    ############################################################################
    # opcodes
    ############################################################################

    def get_laser_can_fire(self):
        return 0 != self.get_cmd(0xef, 0, 1)[0]

    def get_laser_is_firing(self):
        return 0 != self.get_cmd(0xff, 0x0d, 1)[0]

    def set_laser_warning_delay_sec(self, sec):
        print(f"Setting laser warning delay to {sec} seconds")
        return self.send_cmd(0x8a, sec)

    def set_laser_watchdog(self, sec):
        print(f"Setting watchdog to {sec} seconds")
        return self.send_cmd(0xff, 0x18, sec)

    def get_battery_level(self):
        raw = self.dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x13, 0, 3, TIMEOUT_MS)
        print("g_b_l(): resp raw : ", raw)
        #raw = self.get_cmd(0xff, 0x13, 3)
        if raw is None or len(raw) < 3:
            return f"ERROR: cannot read battery: {raw}"
        percentage = raw[1] + (1.0 * raw[0] / 256.0)
        charging = raw[2] != 0
        return f"%s (%.2f%%) (%s)" % (raw, percentage, "charging" if charging else "not charging")

    def set_enable(self, flag):
        print("setting LASER_ENABLE %s" % ("on" if flag else "off"))
        self.send_cmd(0xbe, 1 if flag else 0)

    def set_modulation_enable(self, flag):
        print("setting LASER_MOD_ENABLE %s" % ("on" if flag else "off"))
        self.send_cmd(0xbd, 1 if flag else 0)

    def set_modulation_params(self, period_us=None, width_us=None):
        if period_us is None:
            period_us = self.args.mod_period_us
        if width_us is None:
            width_us = self.args.mod_width_us

        if period_us > 0xffff or width_us > 0xffff:
            print("error: lame script doesn't support full 40-bit 5-byte args")
            return

        # should we modulate after all?
        if period_us <= width_us:
            print("disabling modulation because period %d <= width %d" % (period_us, width_us))
            self.set_modulation_enable(False)
            return

        print(f"setting LASER_MOD_PULSE_PERIOD {period_us}")
        self.send_cmd(0xc7, period_us, buf=[0]*8)

        print(f"setting LASER_MOD_PULSE_WIDTH {width_us}")
        self.send_cmd(0xdb, width_us, buf=[0]*8)

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

    def send_cmd(self, cmd, value, index=0, buf=None, label=None):
        if buf is None:
            if self.is_arm():
                buf = [0] * 8
            else:
                buf = 0
        self.debug(f"ctrl_transfer(bmRequestType 0x{HOST_TO_DEVICE:02x}, bRequest 0x{cmd:02x}, wValue 0x{value:04x}, wIndex 0x{index:04x}) >> {buf}")
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)


    def get_cmd(self, cmd, value=0, index=0, length=64):
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        self.debug(f"ctrl_transfer(bmRequestType 0x{DEVICE_TO_HOST:02x}, bRequest 0x{cmd:02x}, wValue 0x{value:04x}, wIndex 0x{index:04x}, wLength {length}) => {result}")
        return result

fixture = Fixture()
if fixture.dev:
    fixture.run()
