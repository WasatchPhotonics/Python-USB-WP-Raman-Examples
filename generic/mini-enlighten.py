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

        self.spectrum_count = 0

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

        self.get_fpga_configuration_register("before 1")

        # 1. read EEPROM
        eeprom = self.read_eeprom()
        print(f"eeprom <- {eeprom}")

        self.get_fpga_configuration_register("after eeprom")

        self.pixels = eeprom["pixels"]
        print(f"pixels <- {self.pixels}")

        # 2. read FPGA compilation options
        fpga_options = self.read_fpga_compilation_options()
        print(f"fpga_compilation_options <- {fpga_options}")

        self.get_fpga_configuration_register("after fpga compilation options")

        # 3. CONFIGURE FPGA (if format >= 4, send gain/offset even/odd downstream)

        if False:
            # 4. set trigger source
            print(f"trigger_source -> 0")
            self.set_trigger_source(0)

            self.get_fpga_configuration_register("after trigger source")

        # 5. set integration time
        print(f"integration_time_ms -> {self.args.integration_time_ms}")
        self.set_integration_time_ms(self.args.integration_time_ms)

        self.get_fpga_configuration_register("after integration time")

        # 6. get FW revision
        fw_rev = self.get_firmware_version()
        print(f"FW Revision <- {fw_rev}")

        self.get_fpga_configuration_register("after FW version")

        # 7. get FPGA revision
        fpga_rev = self.get_fpga_version()
        print(f"FPGA Revision <- {fpga_rev}")

        self.get_fpga_configuration_register("after FPGA version")

        # 8. get integration time (verify it was set correctly)
        ms = self.get_integration_time_ms()
        print(f"integration_time_ms <- {ms}")
        if ms != self.args.integration_time_ms:
            print(f"integration time didn't match expectation ({ms} != {self.args.integration_time_ms})")

        self.get_fpga_configuration_register("after getting integration time")

        # 9. get detector gain
        gain = self.get_detector_gain()
        print(f"detector gain <- {gain:0.3f}")

        self.get_fpga_configuration_register("after getting gain")

        print("finished ENLIGHTEN connection sequence")

    def run(self):
        outfile = open(self.args.outfile, 'w') if self.args.outfile is not None else None
        for i in range(self.args.spectra):
            spectrum = self.get_spectrum()
            print("Spectrum %3d/%3d %s ..." % (i, self.args.spectra, spectrum[:10]))
            if outfile is not None:
                outfile.write("%s, %s\n" % (datetime.now(), ", ".join([str(x) for x in spectrum])))

            raw_temp = self.get_detector_temperature_raw()
            print("Raw temperature %04x" % raw_temp)
        if outfile is not None:
            outfile.close()

    ############################################################################
    # opcodes
    ############################################################################

    ##
    # @note there is no 0xb3 GET_FPGA_CONFIGURATION_REGISTER in ENG-0001 -- this
    # was for an internal FW test
    def get_fpga_configuration_register(self, label=""):
        # raw = self.get_cmd(0xb3, lsb_len=2)
        # print(f"FPGA Configuration Register: 0x{raw:04x} ({label})")
        pass

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

    def get_detector_temperature_raw(self):
        self.get_fpga_configuration_register(f"before GET_CCD_TEMP")
        result = self.get_cmd(0xd7, label="GET_CCD_TEMP", msb_len=2)
        self.get_fpga_configuration_register(f"after GET_CCD_TEMP")
        return result

    def set_detector_tec_setpoint(self, raw):
        self.get_fpga_configuration_register(f"before SET_DETECTOR_TEC_SETPOINT")
        self.set_cmd(0xd8, wValue=0xa46, label="SET_DETECTOR_TEC_SETPOINT")
        self.get_fpga_configuration_register(f"after SET_DETECTOR_TEC_SETPOINT")

    ## @see wasatch.FeatureIdentificationDevice.get_line
    def get_spectrum(self):
        self.get_fpga_configuration_register(f"before spectrum {self.spectrum_count}")
        timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2
        self.send_cmd(0xad, 1)

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
            timeout_ms = self.args.integration_time_ms * 8 + 500
        else:
            timeout_ms = self.args.integration_time_ms * 2 + 1000 

        spectrum = []
        for endpoint in endpoints:
            self.debug(f"waiting for {block_len_bytes} bytes from endpoint 0x{endpoint:02x} (timeout {timeout_ms}ms)")
            data = self.device_type.read(self.device, endpoint, block_len_bytes, timeout=timeout_ms)
            log.debug("read %d bytes", len(data))

            subspectrum = [int(i | (j << 8)) for i, j in zip(data[::2], data[1::2])] # LSB-MSB
            spectrum.extend(subspectrum)

            # empirically determined need for 5ms delay when switching endpoints
            # on 2048px detectors during area scan
            if self.pixels == 2048 and self.pid != 0x4000: 
                log.debug("sleeping 5ms between endpoints")
                sleep(0.005)

        if len(spectrum) != self.pixels:
            print(f"This is an obviously incomplete spectrum (received {len(spectrum)}, expected {self.pixels})")

        self.get_fpga_configuration_register(f"after spectrum {self.spectrum_count}")

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
