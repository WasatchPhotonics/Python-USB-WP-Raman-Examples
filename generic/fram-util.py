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
TIMEOUT_MS = 10000
PAGES_PER_SPECTRA = 62

PAGE_SIZE = 64
EEPROM_FORMAT = 8

class Fixture(object):
    def __init__(self):
        self.fram_pages = None
        self.subformat = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",          action="store_true",    help="debug output")
        parser.add_argument("--dump",           action="store_true",    help="just dump and exit (default)")
        parser.add_argument("--pid",            default="1000",         help="USB PID in hex (default 1000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--restore",        type=str,               help="restore an FRAM from text file (future dev)")
        parser.add_argument("--fram-pages",     type=int,               help="number of pages to read from FRAM (default 61)", default=61)
        parser.add_argument("--erase",          action="store_true",    help="erase all")
        parser.add_argument("--spectrum-index", type=int,               help="spectrum index", default=0)
        self.args = parser.parse_args()

        if not (self.args.dump):
            self.args.dump = True

        self.pid = int(self.args.pid, 16)
        

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        self.read_fram()
        self.dump_fram()


        if self.args.restore:
            self.restore()
        elif self.args.erase:
            self.erase_fram()
            return
            
        if self.args.dump:
            return
            
        # global settings
        self.pack((0, 63, 1), "B", FRAM_FORMAT)
        if self.subformat is not None:
            self.pack((5, 63, 1), "B", self.subformat)

        self.dump_fram("Proposed")


        cont = input("\nWrite FRAM? (y/N)")
        if cont.lower() != "y":
            print("Cancelled")
            return

        self.write_fram()

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

    def read_fram(self):
        print("Reading FRAM:")
        self.fram_pages = []
        for i in range(self.args.fram_pages):
            buf = self.get_cmd(cmd=0xff, value=0x25, index=(i + self.args.spectrum_index) , length=PAGE_SIZE)
            self.fram_pages.extend(buf)
            sleep(0.1)

    def dump_fram(self, state="Current"):
        print("%s FRAM:" % state)
        spectrum = []
        for i in range(0, len(self.fram_pages), 2):
            spectrum.append(self.fram_pages[i] | (self.fram_pages[i+1] << 8))
        for num, pixel in enumerate(spectrum, start = 1):
            print("Pixel {}: {}" .format(num, pixel))

    def write_fram(self):
        print("Not yet implemented")

    def erase_fram(self):
        print("FRAM erased")
        self.send_cmd(cmd=0xff, value=0x26)
        
        

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

        if page > len(self.fram_pages):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (label %s)" % ( 
                page, start_byte, length, data_type, label))
            return

        buf = self.fram_pages[page]
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

        if page > len(self.fram_pages):
            raise Exception("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (label %s)" % (
                page, start_byte, length, data_type, label))

        # don't try to write negatives to unsigned types
        if data_type in ["H", "I"] and value < 0:
            self.debug("rounding negative to zero when writing to unsigned field (address %s, data_type %s, value %s)" % (address, data_type, value))
            value = 0

        buf = self.fram_pages[page]
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


fixture = Fixture()
if fixture.dev:
    fixture.run()

