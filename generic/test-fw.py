#!/usr/bin/env python

import traceback
import usb.core
import argparse
import struct
import numpy as np
import sys
import re
import os

from time import sleep
from datetime import datetime

import EEPROMFields

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

MAX_PAGES = 8
PAGE_SIZE = 64
EEPROM_FORMAT = 8

class Fixture:

    def __init__(self):
        self.eeprom_fields = EEPROMFields.get_eeprom_fields()
        self.eeprom_pages = None
        self.eeprom = {}

        self.detail_report = ""

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--pid", type=str, default="4000")
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--verbose", action="store_true", help="append detail report")

        # for reading spectra
        parser.add_argument("--pixels", type=int, help="override EEPROM active_pixels_horizontal")
        parser.add_argument("--spectra", type=int, default=10, help="how many spectra to read")
        parser.add_argument("--outfile", type=str, help="if provided, will receive row-ordered spectra in CSV")

        # for resetting after tests (could use EEPROM start fields...)
        parser.add_argument("--integration-time-ms", type=int, default=100)
        parser.add_argument("--detector-gain", type=float, default=1.9)

        for name in [ "read-firmware-rev", 
                      "read-fpga-rev", 
                      "read-eeprom", 
                      "read-spectra",
                      "test-integration-time",
                      "test-detector-gain",
                      "test-vertical-roi" ]:
            parser.add_argument(f"--{name}", default=True, action=argparse.BooleanOptionalAction)
        self.args = parser.parse_args()

        self.pid = int(self.args.pid, 16)
        self.device = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.device:
            print("No spectrometer found with PID 0x%04x" % self.pid)
            sys.exit(1)

        if os.name == "posix":
            self.debug("claiming interface")
            self.device.set_configuration(1)
            usb.util.claim_interface(self.device, 0)

    def run(self):

        if self.args.read_firmware_rev:
            self.report("Firmware Revision", self.get_firmware_version())

        if self.args.read_fpga_rev:
            self.report("FPGA Revision", self.get_fpga_version())

        if self.args.read_eeprom:
            self.report("EEPROM Read", self.read_eeprom())

        if self.args.read_spectra:
            self.report("Read Spectra", self.read_spectra())

        if self.args.test_integration_time:
            self.report("Integration Time", self.test_integration_time())

        if self.args.test_detector_gain:
            self.report("Detector Gain", self.test_detector_gain())

        if self.args.test_vertical_roi:
            self.report("Vertical ROI", self.test_vertical_roi())

        if self.args.verbose:
            print("\nVerbose report:")
            print("---------------------------------------------------------")
            print(self.detail_report)

    ############################################################################
    # tests
    ############################################################################

    def get_firmware_version(self):
        result = self.get_cmd(0xc0)
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self):
        result = self.get_cmd(0xb4)
        if result is not None:
            return "".join([chr(c) for c in result if 0x20 <= c <= 0x7f])

    def read_eeprom(self):
        self.eeprom_pages = [self.get_cmd(0xff, 0x01, page) for page in range(8)]
        
        self.eeprom = {}
        for name in self.eeprom_fields:
            field = self.eeprom_fields[name]
            self.eeprom[name] = self.unpack(field.pos, field.data_type, name)

        self.detail_report += "\nEEPROM:\n"
        for name in self.eeprom:
            self.detail_report += f"  {name + ':':30s} {self.eeprom[name]}\n"

        return f"{len(self.eeprom_pages)} pages read"

    def read_spectra(self):
        self.set_integration_time_ms(self.args.integration_time_ms)

        self.detail_report += "\nRead Spectra:\n"
        all_start = datetime.now()    
        for i in range(self.args.spectra):
            this_start = datetime.now()    
            spectrum = self.get_spectrum(label="Read Spectra")
            this_elapsed = (datetime.now() - this_start).total_seconds()

            mean = np.mean(spectrum)
            self.detail_report += f"  {this_start}: read spectrum {i} of {len(spectrum)} pixels in {this_elapsed:0.2f}sec with mean {mean:0.2f} at {self.args.integration_time_ms}ms\n"
        all_elapsed = (datetime.now() - all_start).total_seconds()

        return f"{self.args.spectra} spectra read in {all_elapsed:0.2f}sec at {self.args.integration_time_ms}ms"

    def test_integration_time(self):
        self.detail_report += "\nIntegration Time:\n"
        values = [10, 100, 400]
        for ms in values:
            self.set_integration_time_ms(ms)
            check = self.get_integration_time_ms()
            if check != ms:
                return f"ERROR: wrote integration time {ms} but read {check}"
                            
            spectrum, mean, elapsed = self.get_averaged_spectrum(ms=ms, label="Integration Time")
            self.detail_report += f"  set/get integration time {ms:4d}ms then read {self.args.spectra} spectra with mean {mean:0.2f} in {elapsed:0.2f}sec\n"

        # reset for subsequent tests
        self.set_integration_time_ms(self.args.integration_time_ms)
        return f"collected {self.args.spectra} spectra at each of {values}ms"

    def test_detector_gain(self):
        self.detail_report += "\nDetector Gain:\n"
        values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 8, 16, 24, 31]
        for dB in values:
            self.set_detector_gain(dB)
            check = self.get_detector_gain()
            epsilon = 0.1 if self.pid == 0x4000 else 0.001
            if abs(check - dB) > epsilon:
                return f"ERROR: wrote gain {dB} but read {check}"

            spectrum, mean, elapsed = self.get_averaged_spectrum(label="Gain")
            self.detail_report += f"  set/get gain {dB:0.1f}dB then read {self.args.spectra} spectra with mean {mean:0.2f} in {elapsed:0.2f}sec\n"

        # reset for subsequent tests
        self.set_detector_gain(self.args.detector_gain)
        return f"collected {self.args.spectra} spectra at each of {values}dB"

    def test_vertical_roi(self):
        self.detail_report += "\nVertical ROI:\n"
        tuples = []
        for start_line in range(100, 1000, 100):
            stop_line = start_line + 100
            tuples.append( (start_line, stop_line) )

            self.set_start_line(start_line)
            if False:
                check = self.get_start_line()
                if check != start_line:
                    return f"ERROR: wrote start line {start_line} but read {check}"

            self.set_stop_line(stop_line)
            if False:
                check = self.get_stop_line()
                if check != stop_line:
                    return f"ERROR: wrote start line {stop_line} but read {check}"

            spectrum, mean, elapsed = self.get_averaged_spectrum(label="Vertical ROI")
            self.detail_report += f"  set/get vertical roi ({start_line}, {stop_line}) then read {self.args.spectra} spectra with mean {mean:0.2f} in {elapsed:0.2f}sec\n"

        # reset for subsequent tests
        self.set_start_line(100)
        self.set_stop_line(900)
        return f"collected {self.args.spectra} spectra at each Vertical ROI {tuples}"

    ############################################################################
    #                                                                          #
    #                                 Opcodes                                  #
    #                                                                          #
    ############################################################################

    ############################################################################
    # Integration Time
    ############################################################################

    def set_integration_time_ms(self, ms):
        ms = max(1, min(0xffff, ms)) # just test 16-bit
        self.send_cmd(0xb2, ms)

    def get_integration_time_ms(self):
        return self.get_cmd(0xbf, lsb_len=3)

    ############################################################################
    # Gain
    ############################################################################

    def set_detector_gain(self, gain):
        raw = self.float_to_uint16(gain)
        self.send_cmd(0xb7, raw)
    
    def get_detector_gain(self):
        result = self.get_cmd(0xc5)
        lsb = result[0] 
        msb = result[1]
        return msb + lsb / 256.0

    ############################################################################
    # Vertical ROI
    ############################################################################

    def set_start_line(self, n):
        self.send_cmd(0xff, 0x21, n)

    def get_start_line(self):
        return self.get_cmd(0xff, 0x22, lsb_len=2)

    def set_stop_line(self, n):
        self.send_cmd(0xff, 0x23, n)

    def get_stop_line(self):
        return self.get_cmd(0xff, 0x24, lsb_len=2)

    ############################################################################
    # Laser TEC Setpoint
    ############################################################################

    def set_laser_tec_setpoint(self, raw):
        self.set_cmd(0xd8, wValue=0xa46)

    def get_detector_temperature_raw(self):
        result = self.get_cmd(0xd7, msb_len=2)
        return result

    ############################################################################
    # Utility Methods
    ############################################################################

    def report(self, name, summary):
        name += ":"
        print(f"{name:30s} {summary}")

    def debug(self, msg):
        if self.args.debug:
            print(f"DEBUG: {msg}")

    def float_to_uint16(self, gain):
        msb = int(round(gain, 5)) & 0xff
        lsb = int((gain - msb) * 256) & 0xff
        return (msb << 8) | lsb

    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            if self.pid == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.device.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None):
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

    def unpack(self, pos, data_type, field):
        """
        Unpack a single field at a given buffer offset of the given datatype.
          
        @param pos        a tuple of the form (page, offset, length)
        @param data_type  see https://docs.python.org/2/library/struct.html#format-characters
        @param field      where to store
        """
        page       = pos[0]
        offset     = pos[1]
        length     = pos[2]
        end_byte   = offset + length

        if page > len(self.eeprom_pages):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (field %s)" % ( 
                page, offset, length, data_type, field))
            return

        buf = self.eeprom_pages[page]
        if buf is None or end_byte > len(buf):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (field %s)" % ( 
                page, offset, length, data_type, buf, field))
            return

        if data_type == "s":
            # This stops at the first NULL, so is not appropriate for binary data (user_data).
            # OTOH, it doesn't currently enforce "printable" characters either (nor support Unicode).
            unpack_result = ""
            for c in buf[offset:end_byte]:
                if c == 0:
                    break
                unpack_result += chr(c)
        else:
            unpack_result = 0 
            try:
                unpack_result = struct.unpack(data_type, buf[offset:end_byte])[0]
            except:
                print("error unpacking EEPROM page %d, offset %d, len %d as %s" % (page, offset, length, data_type))
                return

        extra = "" if field is None else f"({field})"
        self.debug(f"Unpacked page {page:02d}, offset {offset:02d}, len {length:02d}, datatype {data_type}: {unpack_result} {extra}")

        return unpack_result

    def get_pixels(self):
        if self.args.pixels is not None:
            return self.args.pixels
        else:
            return self.eeprom.get("active_pixels_horizontal", 1952)

    def get_averaged_spectrum(self, ms=None, count=None, label=None):
        if ms is None:
            ms = self.args.integration_time_ms
        if count is None:
            count = self.args.spectra

        start = datetime.now()    
        summed = self.get_spectrum(ms=ms, label=label)
        for i in range(1, count):
            spectrum = self.get_spectrum(ms=ms, label=label)
            for px in range(len(summed)):
                summed[px] += spectrum[px]
        for px in range(len(summed)):
            summed[px] /= count

        elapsed = (datetime.now() - start).total_seconds()
        mean = np.mean(spectrum)
        return summed, mean, elapsed

    def get_spectrum(self, ms=None, label=None):
        if ms is None:
            ms = self.args.integration_time_ms
        pixels = self.get_pixels()

        timeout_ms = TIMEOUT_MS + ms * 2
        self.send_cmd(0xad, 0)

        endpoints = [0x82]
        block_len_bytes = pixels * 2
        if self.pid != 0x4000 and pixels == 2048:
            endpoints = [0x82, 0x86]
            block_len_bytes = 2048

        if self.pid == 0x4000:
            timeout_ms = ms * 8 + 500
        else:
            timeout_ms = ms * 2 + 1000 

        spectrum = []
        for endpoint in endpoints:
            self.debug(f"waiting for {block_len_bytes} bytes from endpoint 0x{endpoint:02x} (timeout {timeout_ms}ms)")
            data = self.device.read(endpoint, block_len_bytes, timeout=timeout_ms)
            self.debug(f"read {len(data)} bytes")

            if len(endpoints) > 1 and len(spectrum) == 0:
                self.debug("sleeping 5ms between endpoints")
                sleep(0.005)

            subspectrum = [int((msb << 8) | lsb) for lsb, msb in zip(data[::2], data[1::2])]
            spectrum.extend(subspectrum)

        if len(spectrum) != pixels:
            print(f"ERROR: incomplete spectrum (received {len(spectrum)}, expected {pixels})")

        mean = np.mean(spectrum)
        if self.args.outfile:
            with open(self.args.outfile, "a") as f:
                f.write(", ".join([label, str(mean)] + [str(x) for x in spectrum]) + "\n")

        return spectrum

fixture = Fixture()
fixture.run()
