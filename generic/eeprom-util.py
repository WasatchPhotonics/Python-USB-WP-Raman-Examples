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

PAGE_SIZE = 64
EEPROM_FORMAT = 8

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None
        self.subformat = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",          action="store_true",    help="debug output")
        parser.add_argument("--dump",           action="store_true",    help="just dump and exit (default)")
        parser.add_argument("--force-offset",   action="store_true",    help="force ARMs to use the old 'offset' write method")
        parser.add_argument("--pid",            default="1000",         help="USB PID in hex (default 1000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--restore",        type=str,               help="restore an EEPROM from text file")
        parser.add_argument("--multi-wavecal",  type=str,               help="file containing 9 wavecals")
        parser.add_argument("--zero-multi",     action="store_true",    help="zero wavecals 1-8 (leave primary)")
        parser.add_argument("--fix-fifth",      action="store_true",    help="fix the fifth wavelcal coefficient, setting it to zero")
        parser.add_argument("--max-pages",      type=int,               help="override standard max pages (default 8)", default=8)
        self.args = parser.parse_args()

        if not (self.args.dump       or \
                self.args.restore    or \
                self.args.zero_multi or \
                self.args.fix_fifth  or \
                self.args.multi_wavecal):
            self.args.dump = True

        self.pid = int(self.args.pid, 16)

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        self.read_eeprom()
        self.dump_eeprom()
        self.dump_wavecals()

        if self.args.dump:
            return

        elif self.args.zero_multi:
            self.zero_multi()

        elif self.args.multi_wavecal:
            pos_coeffs = self.load_multi()
            for pos, coeffs in pos_coeffs.items():
                self.update_wavecal_coeffs(pos, coeffs)

        elif self.args.fix_fifth:
            self.fix_fifth()

        elif self.args.restore:
            self.restore()

        # global settings
        self.pack((0, 63, 1), "B", EEPROM_FORMAT)
        if self.subformat is not None:
            self.pack((5, 63, 1), "B", self.subformat)

        self.dump_eeprom("Proposed")
        self.dump_wavecals("Proposed")

        cont = input("\nWrite EEPROM? (y/N)")
        if cont.lower() != "y":
            print("Cancelled")
            return

        self.write_eeprom()

    def restore(self):
        linecount = 0
        filetype = None
        print("restoring from %s" % self.args.restore)
        with open(self.args.restore) as f:
            for line in f:
                self.debug("read: %s" % line)
                line = line.strip()
                if line.startswith("#") or len(line) == 0:
                    continue

                linecount += 1
                values = None
                page = None

                # use first (valid) line to determine filetype
                if linecount == 1:
                    if "wasatch.FeatureIdentificationDevice" in line and "GET_MODEL_CONFIG" in line:
                        # 2020-03-19 12:05:41,726 Process-2  wasatch.FeatureIdentificationDevice DEBUG    GET_MODEL_CONFIG(0): get_code: request 0xff value 0x0001 index 0x0000 = [array('B', [87, 80, 45, 55, 56, 53, 45, 88, 45, 83, 82, 45, 83, 0, 0, 0, 87, 80, 45, 48, 48, 53, 54, 49, 0, 0, 0, 0, 0, 0, 0, 0, 44, 1, 0, 0, 1, 0, 0, 17, 3, 50, 0, 2, 0, 10, 0, 0, 51, 51, 243, 63, 0, 0, 51, 51, 243, 63, 0, 0, 0, 0, 0, 6])]
                        filetype = "ENLIGHTEN_LOG"
                    elif re.match(r"Page\s+\d+:\s*array\('B',\s*\[", line):
                        # Page 0: array('B', [83, 105, 71, 45, 55, 56, 53, 0, 0, 0, 0, 0, 0, 0, 0, 0, 87, 80, 45, 48, 48, 54, 52, 54, 0, 0, 0, 0, 0, 0, 0, 0, 44, 1, 0, 0, 0, 1, 1, 2, 0, 25, 0, 15, 0, 15, 0, 0, 0, 0, 0, 65, 0, 0, 51, 51, 243, 63, 0, 0, 0, 0, 0, 9])
                        filetype = "eeprom-util"
                    else:
                        raise Exception("ERROR: could not determine filetype")
                    self.debug("filetype: %s" % filetype)

                if filetype == "ENLIGHTEN_LOG":
                    m = re.search("GET_MODEL_CONFIG\((\d)\)", line)
                    if not m:
                        raise Exception("can't parse page number")
                    page = int(m.group(1))
                    m = re.search("array\('B', \[([0-9, ]+)\]\)", line)
                    if not m:
                        raise Exception("can't parse data")
                    delimited = m.group(1)
                    values = [ int(v.strip()) for v in delimited.split(",")]
                
                elif filetype == "eeprom-util":
                    m = re.search(r"""Page\s+(\d+)\s*:\s*array\('B',\s*\[(.*)\]\)""", line)
                    if not m:
                        raise Exception("could not parse line: %s" % line)
                    page = int(m.group(1))
                    if not (0 <= page <= self.args.max_pages):
                        raise Exception("invalid page")
                    delimited = m.group(2)
                    values = [ int(v.strip()) for v in delimited.split(",")]
                        
                else:
                    raise Exception("Unsupported filetype: %s" % filetype)

                if page is None or values is None:
                    raise Exception("could not parse line: %s" % line)

                if not (0 <= page <= self.args.max_pages):
                    raise Exception("invalid page")

                if len(values) != 64:
                    raise Exception("wrong array length")

                self.debug("packing %d values" % len(values))
                for i in range(len(values)):
                    v = values[i]
                    if not (0 <= v <= 255):
                        raise Exception("invalid byte")
                    self.pack((page, i, 1), "B", values[i])
                self.debug("parsed and packed page %d" % page)

    ##
    # Custom command: zero-out 5th wavecal coeff (recently added to EEPROM)
    def fix_fifth(self):
        print("zeroing wavecal coeff[4]")
        self.pack((2, 21, 4), "f", 0.0) 

    def zero_multi(self):             
        coeffs = [ 0, 0, 0, 0 ]
        for i in range(8):
            print("zeroing wavecal %d" % (i + 1));
            self.update_wavecal_coeffs(i + 1, [0, 0, 0, 0])

    def load_multi(self):
        self.subformat = 3
        pos_coeffs = {}
        with open(self.args.wavecal) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or len(line) == 0:
                    continue

                (pos, c0, c1, c2, c3) = line.split(",")
                pos = int(pos)
                pos_coeffs[pos] = [ float(c0), float(c1), float(c2), float(c3) ]
        return pos_coeffs

    def get_page_start(self, pos):
        if pos == 0:
            page = 1
            start = 0
        else:
            page = 6 if pos < 5 else 7
            start = ((pos - 1) % 4) * 16
        return (page, start)

    def update_wavecal_coeffs(self, pos, coeffs):
        print("updating coeffs for pos %d: %s" % (pos, coeffs))

        if pos < 0 or pos > 8:
            raise Exception("invalid grating position (valid positions 1-8)")

        if coeffs is None or len(coeffs) != 4:
            raise Exception("invalid coeffs for pos %d: %s" % (pos, coeffs))

        (page, start) = self.get_page_start(pos)

        for i in range(len(coeffs)):
            self.pack((page, start + i * 4, 4), "f", coeffs[i])

    def read_eeprom(self):
        print("Reading EEPROM:")
        self.eeprom_pages = []
        for page in range(self.args.max_pages):
            buf = self.get_cmd(cmd=0xff, value=0x01, index=page, length=PAGE_SIZE)
            self.eeprom_pages.append(buf)

    def dump_eeprom(self, state="Current"):
        print("%s EEPROM:" % state)
        for page in range(len(self.eeprom_pages)):
            print("  Page %d: %s" % (page, self.eeprom_pages[page]))

    def write_eeprom(self):
        print("Writing EEPROM")
        for page in range(len(self.eeprom_pages)):
            buf = self.eeprom_pages[page]
            print("  writing page %d: %s" % (page, buf))

            if self.pid == 0x4000 and not self.args.force_offset:
                self.send_cmd(cmd=0xff, value=0x02, index=page, buf=buf)
            else:
                DATA_START = 0x3c00
                offset = DATA_START + page * 64 
                self.send_cmd(cmd=0xa2, value=offset, index=0, buf=buf)
            sleep(0.2)

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

        # if label is None:
        #     self.debug("Unpacked [%s]: %s" % (data_type, unpack_result))
        # else:
        #     self.debug("Unpacked [%s]: %s (%s)" % (data_type, unpack_result, label))
        return unpack_result

    ## 
    # Marshall or serialize a single field at a given buffer offset of the given datatype.
    #
    # @param address    a tuple of the form (buf, offset, len)
    # @param data_type  see https://docs.python.org/2/library/struct.html#format-characters
    # @param value      value to serialize
    def pack(self, address, data_type, value):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        if page > len(self.eeprom_pages):
            raise Exception("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (label %s)" % (
                page, start_byte, length, data_type, label))

        # don't try to write negatives to unsigned types
        if data_type in ["H", "I"] and value < 0:
            self.debug("rounding negative to zero when writing to unsigned field (address %s, data_type %s, value %s)" % (address, data_type, value))
            value = 0

        buf = self.eeprom_pages[page]
        if buf is None or end_byte > 64: # byte [63] for revision
            raise Exception("error packing EEPROM page %d, offset %2d, len %2d as %s: buf is %s" % (
                page, start_byte, length, data_type, buf))

        if data_type == "s":
            for i in range(min(length, len(value))):
                if i < len(value):
                    buf[start_byte + i] = ord(value[i])
                else:
                    buf[start_byte + i] = 0
        else:
            struct.pack_into(data_type, buf, start_byte, value)

        # self.debug("Packed (%d, %2d, %2d) '%s' value %s -> %s" % (page, start_byte, length, data_type, value, buf[start_byte:end_byte]))

    def dump_wavecals(self, state="Current"):
        print("%s Wavecals:" % state)
        for pos in range(9):
            (page, start) = self.get_page_start(pos)
            coeffs = []
            for i in range(4):
                coeffs.append(self.unpack((page, start + i * 4, 4), "f"))
            print("  Pos %d: %s" % (pos, coeffs))

fixture = Fixture()
if fixture.dev:
    fixture.run()

# @par Multi-Wavecal
#
# This was originally for Sandbox units with moveable gratings where multiple 
# 3rd-order wavecals are desired to be stored on the EEPROM.  It reads a file 
# like this:
# 
#     # pos, coeff0, coeff1, coeff2, coeff3
#     0, 7.31218E+02, 2.50578E-01, -5.00670E-06, -2.43241E-08
#     1, 7.26996E+02, 2.54947E-01, -5.21551E-06, -2.48926E-08
#     2, 7.27856E+02, 2.36300E-01,  2.84885E-05, -4.16291E-08
#     3, 7.14525E+02, 2.92230E-01, -6.05089E-05,  6.15874E-09
#     4, 7.11584E+02, 2.90810E-01, -5.67034E-05,  5.66710E-09
#     5, 7.09098E+02, 2.85220E-01, -4.59783E-05,  1.85891E-09
#     6, 7.07605E+02, 2.75729E-01, -3.05849E-05, -4.12326E-09
#     7, 7.04131E+02, 2.69440E-01, -1.32936E-05, -1.42876E-08
#     8, 6.99588E+02, 2.72788E-01, -1.61517E-05, -1.21567E-08
#
# Position 0 is written to the standard wavecal location (per ENG-0034).
# Positions 1-4 are written to EEPROM page 6, and positions 5-8 written to
# EEPROM page 7.
#
# Notes:
#   - EEPROM format is updated to rev 7
#   - EEPROM subformat set to 3
#   - Coeff5 on standard wavecal is set to 0.0
#
# Per ENG-0034, EEPROM format for pages 6-7 (subformat 3) is:
#
#   Page    Bytes   Field               Format
#   6        0- 3   Wavecal 1 Coeff 0   float32
#   6        4- 7   Wavecal 1 Coeff 1   float32
#   6        8-11   Wavecal 1 Coeff 2   float32
#   6       12-15   Wavecal 1 Coeff 3   float32
#   6       16-19   Wavecal 2 Coeff 0   float32
#   6       20-23   Wavecal 2 Coeff 1   float32
#   6       24-27   Wavecal 2 Coeff 2   float32
#   6       28-31   Wavecal 2 Coeff 3   float32
#   6       32-35   Wavecal 3 Coeff 0   float32
#   6       36-39   Wavecal 3 Coeff 1   float32
#   6       40-43   Wavecal 3 Coeff 2   float32
#   6       44-47   Wavecal 3 Coeff 3   float32
#   6       48-51   Wavecal 4 Coeff 0   float32
#   6       52-55   Wavecal 4 Coeff 1   float32
#   6       56-59   Wavecal 4 Coeff 2   float32
#   6       60-63   Wavecal 4 Coeff 3   float32
#
#   Page    Bytes   Field               Format
#   7        0- 3   Wavecal 5 Coeff 0   float32
#   7        4- 7   Wavecal 5 Coeff 1   float32
#   7        8-11   Wavecal 5 Coeff 2   float32
#   7       12-15   Wavecal 5 Coeff 3   float32
#   7       16-19   Wavecal 6 Coeff 0   float32
#   7       20-23   Wavecal 6 Coeff 1   float32
#   7       24-27   Wavecal 6 Coeff 2   float32
#   7       28-31   Wavecal 6 Coeff 3   float32
#   7       32-35   Wavecal 7 Coeff 0   float32
#   7       36-39   Wavecal 7 Coeff 1   float32
#   7       40-43   Wavecal 7 Coeff 2   float32
#   7       44-47   Wavecal 7 Coeff 3   float32
#   7       48-51   Wavecal 8 Coeff 0   float32
#   7       52-55   Wavecal 8 Coeff 1   float32
#   7       56-59   Wavecal 8 Coeff 2   float32
#   7       60-63   Wavecal 8 Coeff 3   float32

