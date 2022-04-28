#!/usr/bin/env python

import array
import json
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

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",          action="store_true",    help="debug output")
        parser.add_argument("--dump",           action="store_true",    help="just dump and exit (default)")
        parser.add_argument("--erase",          action="store_true",    help="erase (write all 0xff)")
        parser.add_argument("--hex",            action="store_true",    help="output in hex")
        parser.add_argument("--force-offset",   action="store_true",    help="force ARMs to use the old 'offset' write method")
        parser.add_argument("--pid",            default="1000",         help="USB PID in hex (default 1000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--restore",        type=str,               help="restore an EEPROM from text file")
        parser.add_argument("--max-pages",      type=int,               help="override standard max pages (default 8)", default=8)
        self.args = parser.parse_args()

        if not (self.args.dump or \
                self.args.restore):
            self.args.dump = True

        self.pid = int(self.args.pid, 16)

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        self.read_eeprom()
        self.dump_eeprom()

        if self.args.erase:
            self.do_erase()
            self.write_eeprom()

        if self.args.dump:
            return

        if self.args.restore:
            self.do_restore()
    
    def do_restore(self):
        self.load(filename = self.args.restore)
        self.dump_eeprom("Proposed")

        cont = input("\nWrite EEPROM? (y/N)")
        if cont.lower() != "y":
            print("Cancelled")
            return

        self.write_eeprom()

    def do_erase(self):
        print("Erasing buffers")
        for page in range(len(self.eeprom_pages)):
            for i in range(PAGE_SIZE):
                self.pack((page, i, 1), "B", 0xff)

    def load(self, filename):
        if filename.endswith(".json"):
            self.load_json(filename)
        else:
            self.load_other(filename)

    def load_json(self, filename):
        with open(filename) as f:
            doc = json.load(f)
        buffers_string = doc["buffers"][1:-2] # strip first/last []

        page_strings = buffers_string.split(", array")
        for page in range(len(page_strings)):
            m = re.search(r"\[(.*)\]", page_strings[page])
            delimited = m.group(1)
            values = [ int(v.strip()) for v in delimited.split(",") ]
            self.pack_page(page, values)

    ##
    # This function will load an EEPROM definition from an external 
    # text file.  It supports a couple of different file formats,
    # including:
    #
    # - extract of ENLIGHTEN logfile
    # - output of this program (eeprom-util.py)
    def load_other(self, filename):
        linecount = 0
        filetype = None
        print(f"restoring from {filename}")

        with open(filename) as f:
            for line in f:
                self.debug("read: %s" % line)
                line = line.strip()
                if line.startswith("#") or len(line) == 0:
                    continue

                linecount += 1
                values = None
                page = None

                ################################################################
                # use first non-blank, non-comment line to determine filetype
                ################################################################

                if linecount == 1:

                    # ENLIGHTEN logfile: 2020-03-19 12:05:41,726 Process-2  wasatch.FeatureIdentificationDevice DEBUG    GET_MODEL_CONFIG(0): get_code: request 0xff value 0x0001 index 0x0000 = [array('B', [87, 80, 45, 55, 56, 53, 45, 88, 45, 83, 82, 45, 83, 0, 0, 0, 87, 80, 45, 48, 48, 53, 54, 49, 0, 0, 0, 0, 0, 0, 0, 0, 44, 1, 0, 0, 1, 0, 0, 17, 3, 50, 0, 2, 0, 10, 0, 0, 51, 51, 243, 63, 0, 0, 51, 51, 243, 63, 0, 0, 0, 0, 0, 6])]
                    if "wasatch.FeatureIdentificationDevice" in line and "GET_MODEL_CONFIG" in line:
                        filetype = "ENLIGHTEN_LOG"

                    # eeprom-util.py: Page 0: array('B', [83, 105, 71, 45, 55, 56, 53, 0, 0, 0, 0, 0, 0, 0, 0, 0, 87, 80, 45, 48, 48, 54, 52, 54, 0, 0, 0, 0, 0, 0, 0, 0, 44, 1, 0, 0, 0, 1, 1, 2, 0, 25, 0, 15, 0, 15, 0, 0, 0, 0, 0, 65, 0, 0, 51, 51, 243, 63, 0, 0, 0, 0, 0, 9])
                    elif re.match(r"Page\s+\d+:\s*array\('B',\s*\[", line):
                        filetype = "eeprom-util"

                    # unknown
                    else:
                        raise Exception("ERROR: could not determine filetype")

                    self.debug(f"filetype: {filetype}")

                ################################################################
                # filetype has been determined, so parse each line as read
                ################################################################

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
                    raise Exception(f"Unsupported filetype: {filetype}")

                if page is None or values is None:
                    raise Exception(f"could not parse line: {line}")

                self.pack_page(page, values)

                self.debug(f"parsed and packed page {page}")

    def pack_page(self, page, values):
        if not (0 <= page <= self.args.max_pages):
            raise Exception(f"invalid page: {page}")

        length = len(values)
        if length != 64:
            raise Exception(f"wrong array length: {length}")

        self.debug(f"packing {length} values")
        for i in range(length):
            v = values[i]
            if not (0 <= v <= 255):
                raise Exception(f"invalid byte: {v}")
            self.pack((page, i, 1), "B", values[i])

    def read_eeprom(self):
        print("Reading EEPROM")
        self.eeprom_pages = []
        for page in range(self.args.max_pages):
            buf = self.get_cmd(cmd=0xff, value=0x01, index=page, length=PAGE_SIZE)
            self.eeprom_pages.append(buf)
    
    def dump_eeprom(self, state="Current"):
        print("%s EEPROM:" % state)
        for page in range(len(self.eeprom_pages)):
            print(f"  Page {page}: ", end='')
            if self.args.hex:
                print(" ".join([f"{i:02x}" for i in self.eeprom_pages[page]]))
            else:
                print(self.eeprom_pages[page])

    def write_eeprom(self):
        print("Writing EEPROM")
        for page in range(len(self.eeprom_pages)):
            buf = self.eeprom_pages[page]
            print(f"  writing page {page}: {buf}")

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
    def unpack_NOT_USED(self, address, data_type, label=None):
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
            raise Exception("error packing EEPROM page %d, offset %d, len %d as %s: invalid page (label %s)" % (
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

fixture = Fixture()
if fixture.dev:
    fixture.run()
