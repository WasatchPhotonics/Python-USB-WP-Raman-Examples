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

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--list",                action="store_true", help="list all spectrometers")
        parser.add_argument("--set-dfu",             action="store_true", help="set matching spectrometers to DFU mode")
        parser.add_argument("--serial-number",       type=str,            help="desired serial number")
        self.args = parser.parse_args()

        # find all supported devices
        self.devices = []
        for pid in [0x1000, 0x2000, 0x4000]:
            devices = usb.core.find(find_all=True, idVendor=0x24aa, idProduct=pid)
            for dev in devices:
                self.debug("found PID 0x%04x" % pid)
                self.devices.append(dev)

        # is this needed?
        for dev in self.devices:
            self.connect(dev)

        # read eeproms
        for dev in self.devices:
            self.read_eeprom(dev)

        # apply filters
        if self.args.serial_number is not None:
            filtered = []
            for dev in self.devices:
                if dev.eeprom["serial_number"] == self.args.serial_number:
                    filtered.append(dev)
                else:
                    self.debug("ignoring %s" % dev.eeprom["serial_number"])
            self.devices = filtered

        if len(self.devices) == 0:
            print("No spectrometers found")

    def connect(self, dev):
        dev.set_configuration(1)
        usb.util.claim_interface(dev, 0)
        self.debug("claimed device")

    def read_eeprom(self, dev):
        buffers = []
        for page in range(8):
            buf = self.get_cmd(dev, 0xff, 0x01, page)
            buffers.append(buf)
        dev.buffers = buffers

        # parse a few handy fields
        dev.eeprom = {}
        dev.eeprom["model"]         = self.unpack(dev, (0,  0, 16), "s")
        dev.eeprom["serial_number"] = self.unpack(dev, (0, 16, 16), "s")

    def run(self):
        if self.args.list:
            for dev in self.devices:
                print("0x%04x %-32s %s" % (dev.idProduct, dev.eeprom["model"], dev.eeprom["serial_number"]))

        if self.args.set_dfu:
            for dev in self.devices:
                self.set_dfu(dev)

    ############################################################################
    # opcodes
    ############################################################################

    def set_dfu(self, dev):
        self.debug("setting DFU on %s" % dev.eeprom["serial_number"])
        self.send_cmd(dev, 0xfe)

    def set_laser_enable(self, dev, flag):
        self.debug("setting laserEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(dev, 0xbe, 1 if flag else 0)

    def set_selected_laser(self, dev, n):
        if n < 0 or n > 0xffff:
            print("ERROR: selectedLaser requires uint16")
            return

        print("setting selectedLaser to %d" % n)
        self.send_cmd(dev, 0xff, 0x15, n)

    def set_selected_adc(self, dev, n):
        if not n in (0, 1):
            print("ERROR: selectedADC requires 0 or 1")
            return

        print("setting selectedADC to %d" % n)
        self.send_cmd(dev, 0xed, n)

    def set_integration_time_ms(self, dev, n):
        if n < 1 or n > 0xffff:
            print("ERROR: integrationTimeMS requires positive uint16")
            return

        print("setting integrationTimeMS to %d" % n)
        self.send_cmd(dev, 0xb2, n)

    def set_modulation_enable(self, dev, flag):
        print("setting laserModulationEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(dev, 0xbd, 1 if flag else 0)

    def set_raman_mode(self, dev, flag):
        print("setting Raman Mode %s" % ("on" if flag else "off"))
        self.send_cmd(dev, 0xff, 0x16, 1 if flag else 0)

    def set_raman_delay_ms(self, dev, ms):
        if ms < 0 or ms > 0xffff:
            print("ERROR: raman delay requires uint16")
            return

        print("setting Raman Delay %d ms" % ms)
        self.send_cmd(dev, 0xff, 0x20, ms)

    def set_watchdog_sec(self, dev, sec):
        if sec < 0 or sec > 0xffff:
            print("ERROR: watchdog requires uint16")
            return

        print("setting Raman Watchdog %d sec" % sec)
        self.send_cmd(dev, 0xff, 0x18, sec)

    def acquire(self, dev):
        print("performing acquire")
        self.send_cmd(dev, 0xad, 1)

    ############################################################################
    # Utility Methods
    ############################################################################

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, dev, cmd, value=0, index=0, buf=None):
        if buf is None:
            if dev.idProduct == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, dev, cmd, value=0, index=0, length=64):
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d)" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS))
        result = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) << %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, result))
        return result

    def unpack(self, dev, address, data_type):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        buf = dev.buffers[page]
        if buf is None or end_byte > len(buf):
            raise("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (label %s)" %
                (page, start_byte, length, data_type, buf, label))

        if data_type == "s":
            result = ""
            for c in buf[start_byte:end_byte]:
                if c == 0:
                    break
                result += chr(c)
        else:
            result = struct.unpack(data_type, buf[start_byte:end_byte])[0]
        return result

fixture = Fixture()
if len(fixture.devices) > 0:
    fixture.run()
