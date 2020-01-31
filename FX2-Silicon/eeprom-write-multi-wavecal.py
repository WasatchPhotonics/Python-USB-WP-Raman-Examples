#!/usr/bin/env python

import sys

# This script is for Sandbox units with moveable gratings where multiple 
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

import traceback
import usb.core
import argparse
import struct
import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
TIMEOUT_MS = 1000
ZZ = [0] * BUFFER_SIZE

MAX_PAGES = 8
PAGE_SIZE = 64
EEPROM_FORMAT = 7
EEPROM_SUBFORMAT = 3

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",   action="store_true", help="debug output")
        parser.add_argument("--pid",     default="1000", choices=["1000", "2000", "4000"], help="USB Product ID (hex) (default 1000)")
        parser.add_argument("--wavecal", type=str, help="file containing 9 wavecals")
        parser.add_argument("--zero",    action="store_true", help="zero wavecals 1-8 (leave primary)")
        self.args = parser.parse_args()

        if not self.args.zero or self.args.wavecal:
            print("must provide --zero or --wavecal")
            sys.exit(1)

        self.pid = int(self.args.pid, 16)

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        self.read_eeprom()
        self.dump_eeprom()

        if self.args.zero:
            coeffs = [ 0, 0, 0, 0 ]
            for i in range(8):
                self.update_wavecal_coeffs(i + 1, [0, 0, 0, 0])
        else:
            pos_coeffs = self.load_file()
            for pos, coeffs in pos_coeffs.items():
                self.update_wavecal_coeffs(pos, coeffs)

        # global settings
        self.pack((0, 63, 1), "B", EEPROM_FORMAT)
        self.pack((5, 63, 1), "B", EEPROM_SUBFORMAT)
        self.pack((2, 21, 4), "f", 0.0) # so-called 5th coeff of default wavecal

        cont = input("Continue? (y/N)")
        if cont.lower() != "y":
            print("Cancelled")
            return

        self.write_eeprom()

    def load_file(self):
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
        for page in range(MAX_PAGES):
            buf = self.read_eeprom_page(cmd=0xff, value=0x01, index=page, length=PAGE_SIZE)
            self.eeprom_pages.append(buf)
            print("  Page %d: %s" % (page, buf))

    def write_eeprom(self):
        print("Writing EEPROM")
        for page in range(MAX_PAGES):
            buf = self.eeprom_pages[page]
            print("  writing page %d: %s" % (page, buf))

            if self.pid == 0x4000:
                self.send_cmd(cmd=0xff, value=0x02, index=page, buf=buf)
            else:
                DATA_START = 0x3c00
                offset = DATA_START + page * 64 
                self.send_cmd(cmd=0xa2, value=offset, index=0, buf=buf)

    ############################################################################
    # Utility Methods
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value, index=0, buf=None):
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def read_eeprom_page(self, cmd, value=0, index=0, length=64):
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

        if label is None:
            self.debug("Unpacked [%s]: %s" % (data_type, unpack_result))
        else:
            self.debug("Unpacked [%s]: %s (%s)" % (data_type, unpack_result, label))
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
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (label %s)" % (
                page, start_byte, length, data_type, label))
            return

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

        self.debug("Packed (%d, %2d, %2d) '%s' value %s -> %s" % (page, start_byte, length, data_type, value, buf[start_byte:end_byte]))

    def dump_eeprom(self):
        print("EEPROM Contents:")
        for pos in range(9):
            (page, start) = self.get_page_start(pos)

            coeffs = []
            for i in range(4):
                coeffs.append(self.unpack((page, start + i * 4, 4), "f"))

            print("  Pos %d: %s" % (pos, coeffs))

fixture = Fixture()
if fixture.dev:
    fixture.run()
