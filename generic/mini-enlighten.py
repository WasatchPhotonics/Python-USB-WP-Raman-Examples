#!/usr/bin/env python

# Reproduce the ENLIGHTEN startup sequence

import traceback
import usb.core
import argparse
import struct
import sys
import re
import os

from time import sleep
from datetime import datetime

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

MAX_PAGES = 8
PAGE_SIZE = 64
EEPROM_FORMAT = 8

# An extensible, stateful "Test Fixture" 
class Fixture(object):

    ############################################################################
    # Lifecycle 
    ############################################################################

    def __init__(self):
        self.eeprom_pages = None
        self.subformat = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--list",                action="store_true", help="list all spectrometers")
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms)", default=100)
        parser.add_argument("--pixels",              type=int,            help="pixels (default 1024)", default=1024)
        parser.add_argument("--spectra",             type=int,            help="read the given number of spectra", default=10)
        parser.add_argument("--pid",                 type=str,            help="desired PID (default 1000)", default="1000")
        parser.add_argument("--outfile",             type=str,            help="outfile to save full spectra")
        self.args = parser.parse_args()

        self.pid = int(self.args.pid, 16)
        self.device = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.device:
            print("No spectrometers found with PID 0x%04x" % self.pid)
            sys.exit(1)

        if os.name == "posix":
            self.debug("claiming interface")
            dev.set_configuration(1)
            usb.util.claim_interface(dev, 0)

    def connect(self):
        print("starting ENLIGHTEN connection sequence")

        self.pixels = self.args.pixels

        # 1. read EEPROM
        eeprom = self.read_eeprom()
        print(f"eeprom <- {eeprom}")

        self.pixels = eeprom["pixels"]
        print(f"pixels <- {self.pixels}")

        # 2. read FPGA compilation options
        fpga_options = self.read_fpga_compilation_options()
        print(f"fpga_compilation_options <- {fpga_options}")

        # 3. CONFIGURE FPGA (if format >= 4, send gain/offset even/odd downstream)

        if False:
            # 4. set trigger source
            print(f"trigger_source -> 0")
            self.set_trigger_source(0)

        # 5. set integration time
        print(f"integration_time_ms -> {self.args.integration_time_ms}")
        self.set_integration_time_ms(self.args.integration_time_ms)

        # 6. get FW revision
        fw_rev = self.get_firmware_version()
        print(f"FW Revision <- {fw_rev}")

        # 7. get FPGA revision
        fpga_rev = self.get_fpga_version()
        print(f"FPGA Revision <- {fpga_rev}")

        # 8. get integration time (verify it was set correctly)
        ms = self.get_integration_time_ms()
        print(f"integration_time_ms <- {ms}")
        if ms != self.args.integration_time_ms:
            print(f"integration time didn't match expectation ({ms} != {self.args.integration_time_ms})")

        # 9. get detector gain
        gain = self.get_detector_gain()
        print(f"detector gain <- {gain:0.3f}")

        # 10. ACQUIRE, read EP2...

        print("finished ENLIGHTEN connection sequence")

    def run(self):
        outfile = open(self.args.outfile, 'w') if self.args.outfile is not None else None
        for i in range(self.args.spectra):
            spectrum = self.get_spectrum()
            print("Spectrum %3d/%3d %s ..." % (i, self.args.spectra, spectrum[:10]))
            if outfile is not None:
                outfile.write("%s, %s\n" % (datetime.now(), ", ".join([str(x) for x in spectrum])))
        if outfile is not None:
            outfile.close()

    ############################################################################
    # opcodes
    ############################################################################

    def read_eeprom(self):
        self.buffers = [self.get_cmd(0xff, 0x01, page) for page in range(8)]

        self.eeprom = {}
        self.eeprom["format"]        = self.unpack((0, 63,  1), "B")
        self.eeprom["model"]         = self.unpack((0,  0, 16), "s")
        self.eeprom["serial_number"] = self.unpack((0, 16, 16), "s")
        self.eeprom["pixels"]        = self.unpack((2, 16,  2), "H")
        return self.eeprom

    def read_fpga_compilation_options(self):
        word = self.get_cmd(0xff, 0x04, label="READ_COMPILATION_OPTIONS", lsb_len=2)

        opts = {}
        opts["integration_time_resolution"] = (word & 0x0007)
        opts["data_header"]                 = (word & 0x0038) >> 3
        opts["has_cf_select"]               = (word & 0x0040) != 0
        opts["laser_type"]                  = (word & 0x0180) >> 7
        opts["laser_control"]               = (word & 0x0e00) >> 9
        opts["has_area_scan"]               = (word & 0x1000) != 0
        opts["has_actual_integ_time"]       = (word & 0x2000) != 0
        opts["has_horiz_binning"]           = (word & 0x4000) != 0
        return opts

    def set_trigger_source(self, value):
        if self.pid == 0x4000:
            return False
        return self.send_cmd(0xd2, value, buf=[0] * 8) # MZ: this is weird...we're sending the buffer on an FX2-only command

    def get_firmware_version(self):
        result = self.get_cmd(0xc0)
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self):
        s = ""
        result = self.get_cmd(0xb4)
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
                    s += chr(c)
        return s

    def set_integration_time_ms(self, n):
        if n < 1 or n > 0xffff:
            print("ERROR: script only supports positive uint16 integration time")
            return
        self.send_cmd(0xb2, n)

    def get_integration_time_ms(self):
        return self.get_cmd(0xbf, lsb_len=3)

    def get_detector_gain(self):
        result = self.get_cmd(0xc5, label="GET_DETECTOR_GAIN")
        lsb = result[0] 
        msb = result[1]
        gain = msb + lsb / 256.0
        return gain

    def get_spectrum(self):
        timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2
        self.send_cmd(0xad, 1)
        data = self.device.read(0x82, self.pixels * 2, timeout=timeout_ms)
        spectrum = []
        for i in range(0, len(data), 2):
            spectrum.append(data[i] | (data[i+1] << 8))
        return spectrum

    ############################################################################
    # Utility Methods
    ############################################################################

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            if self.pid == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.device.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None):
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d)" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS))
        result = self.device.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) << %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, result))

        value = 0
        if msb_len is not None:
            for i in range(msb_len):
                value = value << 8 | result[i]
            return value
        elif lsb_len is not None:
            for i in range(lsb_len):
                value = (result[i] << (8 * i)) | value
            return value
        else:
            return result

    def unpack(self, address, data_type):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        buf = self.buffers[page]
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
fixture.connect()
fixture.run()
