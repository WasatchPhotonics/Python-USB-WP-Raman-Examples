#!/usr/bin/env python

# Reproduce the Wasatch.NET startup sequence, but in Python

import traceback
import usb.core
import platform
import argparse
import struct
import sys
import re
import os

from time import sleep
from datetime import datetime

import EEPROMFields

if platform.system() == "Darwin":
    from ctypes import *
    from CoreFoundation import *
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

MAX_PAGES = 8
PAGE_SIZE = 64
EEPROM_FORMAT = 8

class Fixture(object):

    ############################################################################
    # Lifecycle 
    ############################################################################

    def __init__(self):
        self.eeprom_pages = None
        self.subformat = None

        self.spectrum_count = 0
        self.timeouts = 0

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--list",                action="store_true", help="list all spectrometers")
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms)", default=100)
        parser.add_argument("--pixels",              type=int,            help="pixels")
        parser.add_argument("--spectra",             type=int,            help="read the given number of spectra", default=10)
        parser.add_argument("--pid",                 type=str,            help="desired PID (default 1000)", default="1000")
        parser.add_argument("--outfile",             type=str,            help="outfile to save full spectra")
        self.args = parser.parse_args()

        self.pid = int(self.args.pid, 16)
        self.device = usb.core.find(idVendor=0x24aa, idProduct=self.pid, backend=backend.get_backend())
        if not self.device:
            print("No spectrometers found with PID 0x%04x" % self.pid)
            sys.exit(1)

        if os.name == "posix":
            self.debug("claiming interface")
            self.device.set_configuration(1)
            usb.util.claim_interface(self.device, 0)
        else:
            self.debug("not on POSIX, so NOT claiming interface")

    def connect(self):
        print("starting Wasatch.NET connection sequence")

        if self.args.pixels is not None:
            self.pixels = self.args.pixels
        elif self.pid == 0x4000:
            self.pixels = 1952
        elif self.pid == 0x2000:
            self.pixels = 512
        else:
            self.pixels = 2048
        self.debug(f"connect: using pixels {self.pixels}")

        # step 1 (EN 4): read EEPROM
        self.read_eeprom()
        print(f"EEPROM:")
        for k, v in self.eeprom.items():
            print(f"  {k:<30s}: {v}")
        self.pixels = self.eeprom["active_pixels_horizontal"]

        # step 2 (EN 7): read FPGA compilation options
        self.read_fpga_compilation_options()
        print(f"FPGA Compilation Options:")
        for k, v in self.fpga_compilation_options.items():
            print(f"  {k:<30s}: {v}")

        # step 3 (EN 1): get FW revision
        fw_rev = self.get_firmware_version()
        print(f"FW Revision: {fw_rev}")

        # step 4 (EN 2): get FPGA revision
        fpga_rev = self.get_fpga_version()
        print(f"FPGA Revision: {fpga_rev}")

        # step 5: set detector TEC setpoint
        if self.eeprom["has_cooling"]:
            degC = None
            if self.eeprom["min_temp"] <= self.eeprom["startup_temp_degC"] <= self.eeprom["max_temp"]:
                degC = self.eeprom["startup_temp_degC"]
            elif re.match(r"7031|10141|9214", self.eeprom["detector"]) or self.is_ingaas():
                degC = -15
            elif re.match(r"16011|11511|11850|13971", self.eeprom["detector"]):
                degC = 10

            if degC is not None:
                self.set_detector_tec_setpoint_degC(degC)

                # step 6:
                self.set_detector_tec_enable(True)

        # step 7 (EN 13): set integration time
        print(f"integration_time_ms -> {self.args.integration_time_ms}")
        self.set_integration_time_ms(self.args.integration_time_ms)

        self.set_laser_mod_linked_to_integration_time(False) # Step 8
        self.set_laser_mod_enable(False) # Step 9
        self.set_laser_enable(False) # Step 10

        # step 11-14 (EN 8-11) send gain/offset even/odd 
        self.set_detector_gain(self.eeprom["gain"])
        self.set_detector_offset(self.eeprom["offset"])
        if self.is_ingaas():
            self.set_detector_gain_odd(self.eeprom["gain_odd"])
            self.set_detector_offset_odd(self.eeprom["offset_odd"])

        # step 15 (EN 3): set high gain mode
        if self.is_ingaas():
            self.set_high_gain_mode_enable(True)

        # step 16 (EN 12): set trigger source
        print(f"trigger_source -> 0")
        self.set_trigger_source(0)

        # step 17-18: get and set laser modulation period
        period_us = self.get_laser_mod_period()
        print(f"laser modulation period {period_us}us")
        period_us = 1000
        self.set_laser_mod_period(period_us)
        print(f"laser modulation period -> {period_us}")

        # step 19-20: get and set laser modulation pulse width
        width_us = self.get_laser_mod_pulse_width()
        print(f"laser modulation width {width_us}us")
        width_us = 99
        self.set_laser_mod_pulse_width(width_us)
        print(f"laser modulation period -> {width_us}")

        # step 21: enable laser modulation
        print("laser mod enable -> True")
        self.set_laser_mod_enable(True)

        print("finished Wasatch.NET connection sequence")

    def is_ingaas(self):
        if self.pid == 0x2000:
            return True
        if self.eeprom["detector"].lower().startswith("g"):
            return True

    def run(self):
        outfile = open(self.args.outfile, 'w') if self.args.outfile is not None else None
        for i in range(self.args.spectra):
            if self.eeprom["has_cooling"]:
                raw_temp = self.get_detector_temperature_raw()
                print(f"Raw detector temperature 0x{raw_temp:04x}")

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

        self.eeprom = EEPROMFields.parse_eeprom_pages(self.buffers)
        # self.eeprom["format"]        = self.unpack((0, 63,  1), "B")
        # self.eeprom["model"]         = self.unpack((0,  0, 16), "s")
        # self.eeprom["serial_number"] = self.unpack((0, 16, 16), "s")
        # self.eeprom["detector"]      = self.unpack((0,  0, 16), "s")
        # self.eeprom["pixels"]        = self.unpack((2, 16,  2), "H")
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
        self.fpga_compilation_options = opts

    def set_laser_mod_linked_to_integration_time(self, flag):
        return self.send_cmd(0xdd, 1 if flag else 0)

    def set_laser_mod_enable(self, flag):
        return self.send_cmd(0xbd, 1 if flag else 0)

    def set_laser_enable(self, flag):
        return self.send_cmd(0xbe, 1 if flag else 0)

    def set_laser_mod_period(self, n):
        return self.send_cmd(0xc7, n)

    def get_laser_mod_period(self):
        return self.get_cmd(0xcb, lsb_len=5)

    def get_laser_mod_pulse_width(self):
        return self.get_cmd(0xdc, lsb_len=5)

    def set_laser_mod_pulse_width(self, n):
        return self.send_cmd(0xdb, n)

    def set_trigger_source(self, value):
        if self.pid == 0x4000:
            return
        buf = [0] * 8
        return self.send_cmd(0xd2, value, buf=buf)

    def set_high_gain_mode_enable(self, flag):
        if self.pid != 0x2000:
            return
        buf = [0] * 8
        return self.send_cmd(0xeb, value=1 if flag else 0, index=0, buf=buf)

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

    def get_laser_enabled(self):
        return 0 != self.get_cmd(0xe2, lsb_len=1)

    def get_integration_time_ms(self):
        return self.get_cmd(0xbf, lsb_len=3)

    def set_detector_offset(self, n):
        self.send_cmd(0xb6, n)

    def set_detector_offset_odd(self, n):
        self.send_cmd(0x9c, n)

    def set_detector_gain(self, n):
        msb = int(n)
        lsb = int((n - msb) * 256)
        raw = (msb << 8) | lsb
        self.send_cmd(0xb7, raw)

    def set_detector_gain_odd(self, n):
        msb = int(n)
        lsb = int((n - msb) * 256)
        raw = (msb << 8) | lsb
        self.send_cmd(0x9d, raw)

    def get_detector_gain(self):
        result = self.get_cmd(0xc5, label="GET_DETECTOR_GAIN")
        lsb = result[0] 
        msb = result[1]
        gain = msb + lsb / 256.0
        return gain

    def get_detector_temperature_raw(self):
        return self.get_cmd(0xd7, label="GET_CCD_TEMP", msb_len=2)

    def set_detector_tec_setpoint_degC(self, raw):
        self.send_cmd(0xd8, raw, label="SET_DETECTOR_TEC_SETPOINT")

    def set_detector_tec_enable(self, flag):
        value = 1 if flag else 0
        self.send_cmd(0xd6, value, label="SET_DETECTOR_TEC_ENABLE")

    ## @see wasatch.FeatureIdentificationDevice.get_line
    def get_spectrum(self):
        timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2
        self.debug(f"using timeout_ms {timeout_ms}")
        self.send_cmd(0xad, 0)

        endpoints = [0x82]
        block_len_bytes = self.pixels * 2
        if self.pixels == 2048 and self.pid != 0x4000: # ARM doesn't need this
            endpoints = [0x82, 0x86]
            block_len_bytes = 2048 # 1024 pixels apiece from two endpoints

        if self.pid == 0x4000:
            # assume all ARMs are IMX (this isn't actually true)
            #
            # we have no idea if microRaman has to "wake up" the sensor, so wait
            # long enough for 6 throwaway frames if need be
            timeout_ms = self.args.integration_time_ms * 8 + 5000
        else:
            timeout_ms = self.args.integration_time_ms * 2 + 1000 

        spectrum = []
        try:
            for endpoint in endpoints:
                self.debug(f"waiting for {block_len_bytes} bytes from endpoint 0x{endpoint:02x} (timeout {timeout_ms}ms)")
                data = self.device.read(endpoint, block_len_bytes, timeout=timeout_ms)
                print(f"read {len(data)} bytes")

                subspectrum = [int(i | (j << 8)) for i, j in zip(data[::2], data[1::2])] # LSB-MSB
                spectrum.extend(subspectrum)

                # empirically determined need for 5ms delay when switching endpoints
                # on 2048px detectors during area scan
                if self.pixels == 2048 and self.pid != 0x4000: 
                    print("sleeping 5ms between endpoints")
                    sleep(0.005)
        except usb.core.USBError as ute:
            self.timeouts += 1
            print(f"ignoring usb.core.USBError number {self.timeouts}")
        except usb.core.USBTimeoutError as ute:
            self.timeouts += 1
            print(f"ignoring usb.core.USBTimeoutError number {self.timeouts}")

        if len(spectrum) != self.pixels:
            print(f"This is an obviously incomplete spectrum (received {len(spectrum)}, expected {self.pixels})")

        self.spectrum_count += 1
        return spectrum

    ############################################################################
    # Utility Methods
    ############################################################################

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value=0, index=0, buf=None, label=None):
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
