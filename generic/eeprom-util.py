#!/usr/bin/env python

import traceback
import argparse
import random
import struct
import array
import json
import sys
import re

from time import sleep
import usb.core

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

PAGE_SIZE = 64

class Fixture(object):
    def __init__(self):
        self.eeprom_pages = None
        self.fields = {}
        self.field_names = []
        self.pattern_count = 0

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",          action="store_true",    help="debug output")
        parser.add_argument("--dump",           action="store_true",    help="just dump and exit (default)")
        parser.add_argument("--erase",          action="store_true",    help="erase (pages filled per --pattern)")
        parser.add_argument("--noparse",        action="store_true",    help="don't parse EEPROM fields")
        parser.add_argument("--pid",            default="1000",         help="USB PID in hex (default 1000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--restore",        type=str,               help="restore an EEPROM from text file")
        parser.add_argument("--set",            action="append",        help="set a name=value pair")
        parser.add_argument("--max-pages",      type=int,               help="override standard max pages (default 8)", default=8)
        parser.add_argument("--reprogram",      action="store_true",    help="overwrites first 8 pages with --pattern, then populates minimal defaults")
        parser.add_argument("--verify",         action="store_true",    help="verifies EEPROM contents match the specified pattern and not immutable string")
        parser.add_argument("--pixels",         type=int,               help="active_pixels_horizontal when reprogramming", default=1024)
        parser.add_argument("--pattern",        type=str,               help="for reprogram or erase, use this base pattern", default="zeros",
                                                                        choices=["zeros", "ones", "random", "ramp", "ramp-all"])
        self.args = parser.parse_args()

        if not (self.args.dump or \
                self.args.erase or \
                self.args.verify or \
                self.args.restore):
            self.args.dump = True

        self.pid = int(self.args.pid, 16)

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        self.read_revs()
        self.read_eeprom()

        if not self.args.noparse:
            self.parse_eeprom()

        self.dump_eeprom()

        if self.args.erase:
            if self.confirm("Preparing to erase EEPROM."):
                self.do_erase()
                self.write_eeprom()
        elif self.args.reprogram:
            self.do_reprogram()
        elif self.args.set:
            self.do_set()
        elif self.args.verify:
            self.do_verify()

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

    def pattern_generator(self):
        if self.args.pattern == "zeros":
            value = 0x00
        elif self.args.pattern == "ones":
            value = 0xff
        elif self.args.pattern == "random":
            value = random.randint(0, 255)
        elif self.args.pattern == "ramp":
            value = self.pattern_count % 64
        elif self.args.pattern == "ramp-all":
            value = self.pattern_count % 256

        self.pattern_count += 1
        return value
        
    def do_erase(self):
        print("Erasing buffers")
        for page in range(len(self.eeprom_pages)):
            for i in range(PAGE_SIZE):
                value = self.pattern_generator()
                self.pack((page, i, 1), "B", value)

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
            print(" ".join([f"{i:02x}" for i in self.eeprom_pages[page]]))

    def write_eeprom(self):
        print("Writing EEPROM")
        for page in range(len(self.eeprom_pages)):
            buf = self.eeprom_pages[page]
            print(f"  writing page {page}: {buf}")

            if self.pid == 0x4000:
                self.send_cmd(cmd=0xff, value=0x02, index=page, buf=buf)
            else:
                DATA_START = 0x3c00
                offset = DATA_START + page * 64 
                self.send_cmd(cmd=0xa2, value=offset, buf=buf)
            sleep(0.2)

    def do_set(self, write=True):
        if self.args.set is None:
            return

        changes = []
        for pair in self.args.set:
            tok = pair.split("=")
            if len(tok) != 2:
                print(f"skipping pair {pair}")
                continue

            k, v = tok
            k = k.lower()

            if k == "startup_integration_time_ms":
                v = int(v)
                self.pack((0, 43, 2), "H", v)
                print(f"changing {k} -> {v}")
            elif k == "startup_temp_degc":
                v = int(v)
                self.pack((0, 45, 2), "h", v)
                print(f"changing {k} -> {v}")
            elif k == "model":
                self.pack((0,  0, 16), "s", v)
            elif k == "serial_number":
                self.pack((0, 16, 16), "s", v)
            elif k == "laser_watchdog_sec":
                self.pack((3, 52, 4), "H", v)
            else:
                print(f"unsupported key: {k} ({v})")
        
        if write:
            self.dump_eeprom("Proposed")
            if not self.confirm("Will re-write EEPROM with updated contents"):
                return
            self.write_eeprom()

    def confirm(self, msg):
        print(msg)
        cont = input("\n\nContinue? (y/N) ")
        return cont.lower() == "y"

    def do_verify(self):
        IMMUTABLE = r"c2 47 05 31 21 00 00 04 00 03 00 00 02 31 a5 00 03 00 33 02 39 0f 00 03 00 43 02 2f 00 00 03 00 " \
                  +  "4b 02 2b 23 00 03 00 53 02 2f 00 03 ff 01 00 90 e6 78 e0 54 10 ff c4 54 0f 44 50 f5 09 13 e4"
        for page in range(self.args.max_pages):
            buf = self.eeprom_pages[page] 
            s = " ".join([f"{v:02x}" for v in buf])
            if s == IMMUTABLE:
                print(f"ERROR: page {page} matches immutable")
                continue
            
            for i in range(len(buf)):
                expected = self.pattern_generator()
                if buf[i] != expected:
                    print(f"ERROR: page {page} did not match {self.args.pattern}: {s}")
                    break

    def do_reprogram(self):
        if not self.confirm("*** HAZARDOUS OPERATION ***\n" +
                           "Reprogram EEPROM to bland defaults? This is a destructive\n" +
                           "operation which will overwrite all configuration data on\n" +
                           "the spectrometer, destroying any factory calibrations."): return
            
        # set all buffers to base pattern
        self.do_erase()

        # minimum set of defaults to allow ENLIGHTEN operation
        self.pack((0, 63,  1), "B", 15,               "format")
        self.pack((0,  0, 16), "s", "WP-FOO",         "model")
        self.pack((0, 16, 16), "s", "WP-00000",       "serial_number")
        self.pack((0, 48,  4), "f", 1,                "gain") 
        self.pack((1,  4,  4), "f", 1,                "wavecal_c1")
        self.pack((2,  0, 16), "s", "unknown",        "detector")
        self.pack((2, 16,  2), "H", self.args.pixels, "active_pixels_horizontal")
        self.pack((2, 25,  2), "H", self.args.pixels, "actual_pixels_horizontal")
        self.pack((3, 40,  4), "I", 1,                "min_integ")
        self.pack((3, 44,  4), "I", 60000,            "max_integ")

        # override the above with any cmd-line overrides
        self.do_set(write=False)

        self.write_eeprom()

    def parse_eeprom(self):
        print("Parsing EEPROM")

        self.format = self.unpack((0, 63,  1), "B", "format")

        # capitals are unsigned
        self.unpack((0,  0, 16), "s", "model")
        self.unpack((0, 16, 16), "s", "serial_number")
        self.unpack((0, 32,  4), "I", "baud_rate")
        self.unpack((0, 36,  1), "?", "has_cooling")
        self.unpack((0, 37,  1), "?", "has_battery")
        self.unpack((0, 38,  1), "?", "has_laser")
        self.unpack((0, 39,  2), "H", "feature_mask")
        self.unpack((0, 39,  2), "H", "excitation_nm")
        self.unpack((0, 41,  2), "H", "slit_um")
        self.unpack((0, 43,  2), "H", "start_integ")
        self.unpack((0, 45,  2), "h", "start_temp")
        self.unpack((0, 47,  1), "B", "start_trigger")
        self.unpack((0, 48,  4), "f", "gain") 
        self.unpack((0, 52,  2), "h", "offset") 
        self.unpack((0, 54,  4), "f", "gain_odd") 
        self.unpack((0, 58,  2), "h", "offset_odd") 
        self.unpack((1,  0,  4), "f", "wavecal_c0")
        self.unpack((1,  4,  4), "f", "wavecal_c1")
        self.unpack((1,  8,  4), "f", "wavecal_c2")
        self.unpack((1, 12,  4), "f", "wavecal_c3")
        self.unpack((1, 16,  4), "f", "degCtoDAC_c0")
        self.unpack((1, 20,  4), "f", "degCtoDAC_c1")
        self.unpack((1, 24,  4), "f", "degCtoDAC_c2")
        self.unpack((1, 28,  2), "h", "max_temp")
        self.unpack((1, 30,  2), "h", "min_temp")
        self.unpack((1, 32,  4), "f", "adcToDegC_c0")
        self.unpack((1, 36,  4), "f", "adcToDegC_c1")
        self.unpack((1, 40,  4), "f", "adcToDegC_c2")
        self.unpack((1, 44,  2), "h", "r298")
        self.unpack((1, 46,  2), "h", "beta")
        self.unpack((1, 48, 12), "s", "cal_date")
        self.unpack((1, 60,  3), "s", "cal_tech")
        self.unpack((2,  0, 16), "s", "detector")
        self.unpack((2, 16,  2), "H", "active_pixels_horizontal")
        self.unpack((2, 18,  1), "B", "laser_warmup_sec")
        self.unpack((2, 19,  2), "H", "active_pixels_vertical")
        self.unpack((2, 21,  4), "f", "wavecal_c4")
        self.unpack((2, 25,  2), "H", "actual_pixels_horizontal")
        self.unpack((2, 27,  2), "H", "roi_horiz_start")
        self.unpack((2, 29,  2), "H", "roi_horiz_end")
        self.unpack((2, 31,  2), "H", "roi_vertical_region_1_start")
        self.unpack((2, 33,  2), "H", "roi_vertical_region_1_end")
        self.unpack((2, 35,  2), "H", "roi_vertical_region_2_start")
        self.unpack((2, 37,  2), "H", "roi_vertical_region_2_end")
        self.unpack((2, 39,  2), "H", "roi_vertical_region_3_start")
        self.unpack((2, 41,  2), "H", "roi_vertical_region_3_end")
        self.unpack((0, 43,  2), "H", "startup_integration_time_ms")
        self.unpack((0, 45,  2), "h", "startup_temp_degC")
        self.unpack((2, 43,  4), "f", "linearity_c0")
        self.unpack((2, 47,  4), "f", "linearity_c1")
        self.unpack((2, 51,  4), "f", "linearity_c2")
        self.unpack((2, 55,  4), "f", "linearity_c3")
        self.unpack((2, 59,  4), "f", "linearity_c4")
        self.unpack((3, 12,  4), "f", "laser_power_c0")
        self.unpack((3, 16,  4), "f", "laser_power_c1")
        self.unpack((3, 20,  4), "f", "laser_power_c2")
        self.unpack((3, 24,  4), "f", "laser_power_c3")
        self.unpack((3, 28,  4), "f", "max_laser_mW")
        self.unpack((3, 32,  4), "f", "min_laser_mW")
        self.unpack((3, 36,  4), "f", "excitation_nm_float")
        self.unpack((3, 40,  4), "I", "min_integ")
        self.unpack((3, 44,  4), "I", "max_integ")
        self.unpack((3, 48,  4), "f", "avg_resolution")
        self.unpack((3, 52,  2), "H", "laser_watchdog_sec")

        for field in self.field_names:
            print("%30s %s" % (field, self.fields[field]))

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
        self.debug("sending ctrl_transfer(%02x, %02x, %04x, %04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64):
        self.debug("reading ctrl_transfer(%02x, %02x, %04x, %04x, len %d)" % (HOST_TO_DEVICE, cmd, value, index, length))
        return self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

    ##  
    # Unpack a single field at a given buffer offset of the given datatype.
    #   
    # @param address    a tuple of the form (buf, offset, len)
    # @param data_type  see https://docs.python.org/2/library/struct.html#format-characters
    # @param field      where to store
    def unpack(self, address, data_type, field):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        if page > len(self.eeprom_pages):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (field %s)" % ( 
                page, start_byte, length, data_type, field))
            return

        buf = self.eeprom_pages[page]
        if buf is None or end_byte > len(buf):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (field %s)" % ( 
                page, start_byte, length, data_type, buf, field))
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

        extra = "" if field is None else f"({field})"
        self.debug(f"Unpacked page {page:02d}, offset {start_byte:02d}, len {length:02d}, datatype {data_type}: {unpack_result} {extra}")

        self.field_names.append(field)
        self.fields[field] = unpack_result

        return unpack_result

    ## 
    # Marshall or serialize a single field at a given buffer offset of the given datatype.
    #
    # @param address    a tuple of the form (buf, offset, len)
    # @param data_type  see https://docs.python.org/2/library/struct.html#format-characters
    # @param value      value to serialize
    def pack(self, address, data_type, value, label=None):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        if page > len(self.eeprom_pages):
            raise Exception("error packing EEPROM page %d, offset %d, len %d as %s: invalid page (label %s)" % (
                page, start_byte, length, data_type, label))

        if data_type.lower() in ["h", "i", "b", "l", "q"]:
            value = int(value)
        elif data_type.lower() in ["f", "d"]:
            value = float(value)

        # don't try to write negatives to unsigned types
        if data_type in ["H", "I"] and value < 0:
            self.debug("rounding negative to zero when writing to unsigned field (address %s, data_type %s, value %s)" % (address, data_type, value))
            value = 0

        buf = self.eeprom_pages[page]
        if buf is None or end_byte > 64: # byte [63] for revision
            raise Exception("error packing EEPROM page %d, offset %2d, len %2d as %s: buf is %s" % (
                page, start_byte, length, data_type, buf))

        if data_type == "s":
            for i in range(length):
                if i < len(value):
                    buf[start_byte + i] = ord(value[i])
                else:
                    buf[start_byte + i] = 0
        else:
            struct.pack_into(data_type, buf, start_byte, value)

        # self.debug("Packed (%d, %2d, %2d) '%s' value %s -> %s" % (page, start_byte, length, data_type, value, buf[start_byte:end_byte]))

    def get_firmware_version(self):
        result = self.get_cmd(0xc0)
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self):
        s = ""
        result = self.get_cmd(0xb4, length=7)
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
                    s += chr(c)
        return s

    def read_revs(self):
        fpga = self.get_fpga_version()
        fw = self.get_firmware_version()
        print(f"FPGA = {fpga}")
        print(f"FW   = {fw}")

fixture = Fixture()
if fixture.dev:
    fixture.run()
