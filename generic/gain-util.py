#!/usr/bin/env python

import sys
import re

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

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None
        self.subformat = None

        self.detector_gain               = 1.9
        self.detector_offset             = 0
        self.detector_gain_odd           = 1.9
        self.detector_offset_odd         = 0

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",          action="store_true",    help="debug output")
        parser.add_argument("--dump",           action="store_true",    help="just dump and exit (default)")
        parser.add_argument("--pid",            default="1000",         help="USB PID in hex (default 1000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--push-gain",      action="store_true",    help="send the EEPROM's gain to the FPGA")
        parser.add_argument("--push-offset",    action="store_true",    help="send the EEPROM's offset to the FPGA")
        self.args = parser.parse_args()

        self.pid = int(self.args.pid, 16)

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        self.read_eeprom()
        self.parse_eeprom()

        if self.args.push_gain:
            self.push_gain()

        if self.args.push_offset:
            self.push_offset()

    def push_gain(self):
        word = self.to_ubfloat16(self.detector_gain)
        self.send_cmd(0xb7, word)

    def push_offset(self):
        self.send_cmd(0xb6, self.detector_offset)

    def read_eeprom(self):
        self.debug("Reading EEPROM")
        self.eeprom_pages = []
        for page in range(MAX_PAGES):
            buf = self.get_cmd(cmd=0xff, value=0x01, index=page, length=PAGE_SIZE)
            self.eeprom_pages.append(buf)
        if self.args.dump:
            self.dump_eeprom()

    def parse_eeprom(self):
        self.format = self.unpack((0, 63,  1), "B", "format")
        if self.format >= 3:
            self.detector_gain       = self.unpack((0, 48,  4), "f", "gain")       # "even pixels" for InGaAs
            self.detector_offset     = self.unpack((0, 52,  2), "h", "offset")     # "even pixels" for InGaAs
            self.detector_gain_odd   = self.unpack((0, 54,  4), "f", "gain_odd")   # InGaAs-only
            self.detector_offset_odd = self.unpack((0, 58,  2), "h", "offset_odd") # InGaAs-only

        if self.args.dump:
            print("gain %.2f, offset %d (odd %.2f, %d)" % (self.detector_gain, 
                                                           self.detector_offset, 
                                                           self.detector_gain_odd, 
                                                           self.detector_offset_odd))

    def dump_eeprom(self, state="Current"):
        print("%s EEPROM:" % state)
        for page in range(len(self.eeprom_pages)):
            print("  Page %d: %s" % (page, self.eeprom_pages[page]))

    ############################################################################
    # Utility Methods
    ############################################################################

    # convert a float (e.g. 1.9) to the unsigned bfloat16 used in FW (e.g. 0x01e6)
    def to_ubfloat16(self, f):
        msb = int(f) & 0xff
        lsb = int((f - msb) * 256) & 0xff
        word = (msb << 8) | lsb
        self.debug("converted %.2f -> 0x%04x" % (f, word))
        return word

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

    ##  
    # Unpack a single field at a given buffer offset of the given datatype.
    #   
    # @param address    a tuple of the form (buf, offset, len)
    # @param data_type  see https://docs.python.org/2/library/struct.html#format-characters
    # @param label      if provided, is included in debug log output
    def unpack(self, address, data_type, label=None):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        if page > len(self.eeprom_pages):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (label %s)" % ( 
                page, start_byte, length, data_type, label))
            return

        buf = self.eeprom_pages[page]
        if buf is None or end_byte > len(buf):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (label %s)" % ( 
                page, start_byte, length, data_type, buf, label))
            return

        if data_type == "s":
            # This stops at the first NULL, so is not appropriate for binary data (user_data).
            # OTOH, it doesn't currently enforce "printable" characters either (nor support Unicode).
            unpack_result = ""
            for c in buf[start_byte:end_byte]:
                if c == 0:
                    break
                unpack_result += chr(c)
        else:
            unpack_result = 0 
            try:
                unpack_result = struct.unpack(data_type, buf[start_byte:end_byte])[0]
            except:
                print("error unpacking EEPROM page %d, offset %d, len %d as %s" % (page, start_byte, length, data_type))
                return

        return unpack_result

################################################################################
# main()
################################################################################

fixture = Fixture()
if fixture.dev:
    fixture.run()
