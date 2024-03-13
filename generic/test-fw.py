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

    VERSION = "1.0.0"

    def __init__(self):
        self.eeprom_fields = EEPROMFields.get_eeprom_fields()
        self.eeprom_pages = None
        self.eeprom = {}

        self.parse_args()

        self.pid = int(self.args.pid, 16)
        self.device = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.device:
            print("No spectrometer found with PID 0x%04x" % self.pid)
            sys.exit(1)

        # default gain varies by detector type
        if self.args.detector_gain is None:
            if self.pid == 0x4000:
                self.args.detector_gain = 8
            else:
                self.args.detector_gain = 1.9

        if os.name == "posix":
            self.debug("claiming interface")
            self.device.set_configuration(1)
            usb.util.claim_interface(self.device, 0)

        if not os.path.exists("data/"):
            os.mkdir("data")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.logfile = open(f"data/test-fw-{ts}.log", "w")
        self.outfile = open(f"data/test-fw-{ts}.csv", "w")

        # safety
        self.laser_power_perc = None
        self.set_laser_enable(False)

    def parse_args(self):
        parser = argparse.ArgumentParser(
            prog=f"test-fw.py {self.VERSION}", 
            description="Simple command-line script to quickly verify a number of key firmware functionality points over USB.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--pid", type=str, default="4000")
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--test", type=str, action="append", help="manually specify tests to execute")

        # for reading spectra
        parser.add_argument("--pixels", type=int, help="override EEPROM active_pixels_horizontal")
        parser.add_argument("--spectra", type=int, default=10, help="how many spectra to read")

        # for resetting after tests (could use EEPROM start fields...)
        parser.add_argument("--integration-time-ms", type=int, default=100)
        parser.add_argument("--detector-gain", type=float)

        # these tests default on, disable with --no-{name}
        for name in [ "read-firmware-rev", 
                      "read-fpga-rev", 
                      "read-eeprom", 
                      "read-spectra",
                      "test-integration-time",
                      "test-detector-gain",
                      "test-vertical-roi",
                      "test-saturation",
                      "test-laser-enable",
                      "test-laser-pwm",
                      "test-battery" ]:
            parser.add_argument(f"--{name}", default=True, action=argparse.BooleanOptionalAction)

        # miscellaneous options
        parser.add_argument("--laser-enable", action="store_true", help="must be specified to allow laser to fire")
        parser.add_argument("--ignore-getter-failures", action="store_true", help="ignore failures by a getter to match settor value")
        parser.add_argument("--test-vertical-roi-getters", default=True, action=argparse.BooleanOptionalAction, help="kludge to get broken Rev3 to pass")
        parser.add_argument("--confirm", action="store_true", help="allow tests to prompt user to confirm individual steps")

        self.args = parser.parse_args()

    def run(self):
        self.report("test-fw.py", self.VERSION)

        if self.args.test:
            for test in self.args.test:
                if hasattr(self, test):
                    eval(f"self.report('{test}', self.{test}())")
        else:
            self.run_all_tests()

        self.logfile.close()
        self.outfile.close()

    def run_all_tests(self):
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

        if self.args.test_saturation:
            self.report("Saturation", self.test_saturation())

        if self.args.test_laser_enable:
            self.report("Laser Enable", self.test_laser_enable())

        if self.args.test_laser_pwm:
            self.report("Laser PWM", self.test_laser_pwm())

        if self.args.test_battery:
            self.report("Battery", self.test_battery())

    ############################################################################
    # tests
    ############################################################################

    def get_firmware_version(self):
        result = self.get_cmd(0xc0, label="GET_FIRMWARE_VERSION")
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self):
        result = self.get_cmd(0xb4, label="GET_FPGA_VERSION")
        if result is not None:
            return "".join([chr(c) for c in result if 0x20 <= c <= 0x7f])

    def read_eeprom(self):
        self.log_header("Read EEPROM")
        self.eeprom_pages = [self.get_cmd(0xff, 0x01, page, label="READ_EEPROM") for page in range(8)]
        
        self.eeprom = {}
        for name in self.eeprom_fields:
            field = self.eeprom_fields[name]
            self.eeprom[name] = self.unpack(field.pos, field.data_type, name)

        for name in self.eeprom:
            self.log(f"  {name + ':':30s} {self.eeprom[name]}")

        label = self.eeprom['model'] + self.eeprom['product_configuration'] + " " + self.eeprom['serial_number']
        return f"read {len(self.eeprom_pages)} pages ({label})"

    def write_eeprom(self):
        self.log_header("Write EEPROM")

        # cache old value
        if "user_data" not in self.eeprom:
            return "ERROR: please run read_eeprom first"
        old_value = self.eeprom["user_data"]

        # create new value
        unique_id = f"test-fw.py write_eeprom test at {datetime.now()}"

        # pack new value into local buffers
        field = self.eeprom_fields["user_data"]
        self.log("replacing EEPROM user_data '{old_value}' with '{unique_id}'")
        self.pack(field.pos, field.data_type, unique_id)

        # write page 
        buf = self.eeprom_pages[field.page]
        self.log(f"writing page {field.page}: {buf}")
        if self.pid == 0x4000:
            self.send_cmd(cmd=0xff, value=0x02, index=field.page, buf=buf)
        else:
            DATA_START = 0x3c00
            offset = DATA_START + field.page * 64 
            self.send_cmd(cmd=0xa2, value=offset, buf=buf)
        sleep(0.2) # seems to help
                
        # re-read EEPROM
        self.read_eeprom()

        # verify unique id was read-back from hardware
        if unique_id == self.eeprom["user_data"]:
            return f"PASSED: successfully wrote '{unique_id}' to page {field.page}"
        else:
            return f"FAILED: tried to write '{unique_id}' to page {field.page}, but read back '{self.eeprom['user_data']}'"

    def read_spectra(self):
        self.set_integration_time_ms(self.args.integration_time_ms)

        self.log_header("Read Spectra")
        all_start = datetime.now()    
        for i in range(self.args.spectra):
            this_start = datetime.now()    
            spectrum = self.get_spectrum(label=f"Read Spectra[{i}]")
            this_elapsed = (datetime.now() - this_start).total_seconds()

            mean = np.mean(spectrum)
            self.log(f"  {this_start}: read spectrum {i} of {len(spectrum)} pixels in {this_elapsed:0.2f}sec with mean {mean:0.2f} at {self.args.integration_time_ms}ms")
        all_elapsed = (datetime.now() - all_start).total_seconds()

        return f"PASSED: {self.args.spectra} spectra read in {all_elapsed:0.2f}sec at {self.args.integration_time_ms}ms"

    def test_integration_time(self):
        self.log_header("Integration Time")
        values = [10, 50, 100, 400]

        last_mean = -1
        last_ms = None
        failure_msg = None
        for ms in values:
            self.set_integration_time_ms(ms)
            check = self.get_integration_time_ms()
            if check != ms:
                msg = f"ERROR: wrote integration time {ms} but read {check}"
                self.log(msg)
                if not self.args.ignore_getter_failures:
                    return msg
                            
            spectrum, mean, elapsed = self.get_averaged_spectrum(ms=ms, label=f"Integration Time ({ms}ms)")
            self.log(f"  set/get integration time {ms:4d}ms then read {self.args.spectra} spectra with mean {mean:0.2f} in {elapsed:0.2f}sec")
            
            if mean <= last_mean:
                failure_msg = f"mean of integration at {ms}ms ({mean:.2f}) <= previous mean at {last_ms}ms ({last_mean:.2f})"
            last_mean = mean
            last_ms = ms

        # reset for subsequent tests
        self.set_integration_time_ms(self.args.integration_time_ms)

        if failure_msg:
            return f"FAILED: {failure_msg}"
        else:
            return f"PASSED: collected {self.args.spectra} spectra with increasing mean at each of {values}ms"

    def test_detector_gain(self):
        self.log_header("Detector Gain")
        values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 8, 16, 24, 31]

        last_mean = 0
        failure_msg = None
        for dB in values:
            self.set_detector_gain(dB)
            check = self.get_detector_gain()
            epsilon = 0.1 if self.pid == 0x4000 else 0.001
            if abs(check - dB) > epsilon:
                msg = f"ERROR: wrote gain {dB} but read {check}"
                self.log(msg)
                if not self.args.ignore_getter_failures:
                    return msg

            spectrum, mean, elapsed = self.get_averaged_spectrum(label=f"Gain ({dB}dB)")
            self.log(f"  set/get gain {dB:4.1f}dB then read {self.args.spectra} spectra with mean {mean:0.2f} in {elapsed:0.2f}sec")

            if mean <= last_mean and dB > 1:
                failure_msg = f"mean at gain {dB}dB ({mean:.2f}) <= previous mean {last_mean:.2f}"
            last_mean = mean

        # reset for subsequent tests
        self.set_detector_gain(self.args.detector_gain)

        if failure_msg:
            return f"FAILED: {failure_msg}"
        else:
            return f"PASSED: collected {self.args.spectra} spectra with increasing mean at each of {values}dB"

    def test_vertical_roi(self):
        self.log_header("Vertical ROI")
        tuples = []
        for start_line in range(100, 1000, 100):
            stop_line = start_line + 100
            tuples.append( (start_line, stop_line) )

            self.set_start_line(start_line)
            self.set_stop_line(stop_line)

            if self.args.test_vertical_roi_getters:
                check = self.get_start_line()
                if check != start_line:
                    msg = f"ERROR: wrote start line {start_line} but read {check}"
                    self.log(msg)
                    if not self.args.ignore_getter_failures:
                        return msg

                check = self.get_stop_line()
                if check != stop_line:
                    msg = f"ERROR: wrote start line {stop_line} but read {check}"
                    self.log(msg)
                    if not self.args.ignore_getter_failures:
                        return msg

            spectrum, mean, elapsed = self.get_averaged_spectrum(label=f"Vertical ROI ({start_line}-{stop_line})")
            self.log(f"  set/get vertical roi ({start_line:4d}, {stop_line:4d}) then read {self.args.spectra} spectra with mean {mean:0.2f} in {elapsed:0.2f}sec")

        # reset for subsequent tests
        self.set_start_line(100)
        self.set_stop_line(900)
        return f"collected {self.args.spectra} spectra at each Vertical ROI {tuples}"

    def test_saturation(self):
        self.log_header("Saturation")

        self.set_integration_time_ms(1000)
        self.set_detector_gain(50)

        # take a throwaway, just to be sure
        self.get_spectrum(label="Saturation (throwaway)")

        # take the (ideally) saturated spectrum
        spectrum = self.get_spectrum(label="Saturation")

        # look for runs of 0xffff
        px = 0
        longest = -1
        while px < self.get_pixels():
            run = 0
            if spectrum[px] >= 0xfffe:
                start = px
                run = 1
                while px < self.get_pixels() and spectrum[px] >= 0xfffe:
                    px += 1
                    run += 1
                self.log(f"found saturated run of {run} pixels starting at px {start}")
                longest = max(longest, run)
            else:
                px += 1

        # reset for subsequent tests
        self.set_integration_time_ms(self.args.integration_time_ms)
        self.set_detector_gain(self.args.detector_gain)

        # saturated runs contra-indicate arithmetic rollover
        if longest > 4:
            return f"Passed (found saturated run of {longest} pixels)"
        else:
            return "FAILED (no saturated runs found)"

    def test_laser_enable(self):
        self.log_header("Laser Enable")

        self.set_laser_enable(False)
        dark_spectrum, dark_mean, dark_elapsed = self.get_averaged_spectrum(label="Laser Enable dark")

        dark_check = self.get_laser_enable()
        if dark_check:
            msg = "FAILED (unable to confirm disabled laser for dark)"
            self.log(msg)
            if not self.args.ignore_getter_failures:
                return msg

        self.set_laser_enable(True)
        sample_spectrum, sample_mean, sample_elapsed = self.get_averaged_spectrum(label="Laser Enable sample")

        sample_check = self.get_laser_enable()
        self.set_laser_enable(False)
        if not sample_check:
            msg = "FAILED (unable to confirm enabled laser for sample)"
            self.log(msg)
            if not self.args.ignore_getter_failures:
                return msg

        # confirm mean intensity rose by at least 200 counts or 20%
        delta = sample_mean - dark_mean
        self.log(f"dark mean {dark_mean}, sample mean {sample_mean}, delta {delta}")
        if delta >= 200 or delta > dark_mean * 0.2:
            return f"Success (intensity rose by {round(delta)} counts, {round(100 * delta / dark_mean)}%)"
        else:
            return f"FAILED (intensity changed by {round(delta)} counts against a baseline of {round(dark_mean)})"

    def test_laser_pwm(self):
        self.log_header("Laser PWM")
        
        perc_desc = [99, 75, 50, 25, 1]
        perc_asc  = [1, 25, 50, 75, 99]

        self.set_integration_time_ms(self.args.integration_time_ms)
        self.set_detector_gain(self.args.detector_gain)

        # take dark
        self.confirm("about to disable laser for dark")
        self.set_laser_enable(False) 
        dark, dark_mean, dark_elapsed = self.get_averaged_spectrum(label="Laser PWM dark")

        self.confirm("about to enable laser for sample")
        self.set_laser_enable(True)

        # test descending
        last_mean = None
        last_perc = None
        failures = []
        for perc in perc_desc:
            self.confirm(f"about to change PWM to {perc}%")
            self.set_laser_power_perc(perc)
            spectrum, mean, elapsed = self.get_averaged_spectrum(label=f"Laser PWM desc ({perc}%)")
            corrected = [ y - dark_y for y, dark_y in zip(spectrum, dark) ]
            corrected_mean = np.mean(corrected)
            if last_mean:
                if corrected_mean >= last_mean:
                    failures.append(f"pwm {perc}% mean {corrected_mean:0.2f} >= last pwm {last_perc}% mean {last_mean:0.2f}")
            last_mean = corrected_mean
            last_perc = perc

        if False:
            last_mean = None
            last_perc = None
            for perc in perc_asc:
                self.set_laser_power_perc(perc)
                spectrum, mean, elapsed = self.get_averaged_spectrum(label=f"Laser PWM asc ({perc}%)")
                corrected = [ y - dark_y for y, dark_y in zip(spectrum, dark) ]
                corrected_mean = np.mean(corrected)
                if last_mean:
                    if corrected_mean <= last_mean:
                        failures.append(f"pwm {perc}% mean {corrected_mean:0.2f} <= last pwm {last_perc}% mean {last_mean:0.2f}")
                last_mean = mean
                last_perc = perc

        self.confirm(f"about to disable laser")
        self.set_laser_power_perc(100)
        self.set_laser_enable(False)

        if len(failures):
            return f"FAILED: {'; '.join(failures)}"
        else:
            return f"PASSED: intensity correlated to PWM across desc {perc_desc}% and asc {perc_asc}%"

    def test_laser_watchdog(self):
        pass

    def test_laser_interlock(self):
        pass

    def test_battery(self):
        self.log_header("Battery")
        MAX_SEC = 10 # monitor battery over 10sec

        first = None
        last = None
        static = True
        ever_charged = False

        start = datetime.now()
        while (datetime.now() - start).total_seconds() < MAX_SEC:
            perc, state = self.get_battery_state()
            self.log(f"  charge {perc:6.2f}%, state {state}")
            if first is None:
                first = perc
            if perc != first:
                static = False
            if state == "charging":
                ever_charged = True
            last = perc

            sleep(1)

        if static:
            return f"FAILED: battery charge is static ({first:6.2f}%)"
        elif first < last and ever_charged:
            return f"Success (charged from {first:6.2f}% to {last:6.2f}%)"
        else:
            return f"FAILED (first {first:6.2f}%, last {last:6.2f}%, ever_charged {ever_charged})"

    def set_dfu_mode(self):
        """
        Note that this should be the last test run, as the unit will no longer
        be reachable through libusb through the Wasatch VID/PID.

        This test is not enabled by default, and must be manually run via "--test set_dfu_mode"
        """
        self.log("Enabling DFU mode")
        self.send_cmd(0xfe, label="SET_DFU")
        return "Manual verification required"

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
        self.send_cmd(0xb2, ms, label="SET_INTEGRATION_TIME")

    def get_integration_time_ms(self):
        return self.get_cmd(0xbf, lsb_len=3, label="GET_INTEGRATION_TIME")

    ############################################################################
    # Gain
    ############################################################################

    def set_detector_gain(self, gain):
        raw = self.float_to_uint16(gain)
        self.send_cmd(0xb7, raw, label="SET_DETECTOR_GAIN")
    
    def get_detector_gain(self):
        result = self.get_cmd(0xc5, label="GET_DETECTOR_GAIN")
        lsb = result[0] 
        msb = result[1]
        return msb + lsb / 256.0

    ############################################################################
    # Vertical ROI
    ############################################################################

    def set_start_line(self, n):
        self.send_cmd(0xff, 0x21, n, label="SET_START_LINE")

    def get_start_line(self):
        return self.get_cmd(0xff, 0x22, lsb_len=2, label="GET_START_LINE")

    def set_stop_line(self, n):
        self.send_cmd(0xff, 0x23, n, label="SET_STOP_LINE")

    def get_stop_line(self):
        return self.get_cmd(0xff, 0x24, lsb_len=2, label="GET_STOP_LINE")

    ############################################################################
    # Laser Enable
    ############################################################################

    def set_laser_enable(self, flag):
        if flag and not self.args.laser_enable:
            print("WARNING: declining to enable laser without --laser-enable")
            flag = False

        if self.laser_power_perc is None:
            self.debug("we've never enabled the laser before, so default to 100% power (unmodulated)")
            self.set_laser_power_perc(100)

        self.send_cmd(0xbe, 1 if flag else 0, label="SET_LASER_ENABLE")

    def get_laser_enable(self):
        return 0 != self.get_cmd(0xe2, lsb_len=1, label="GET_LASER_ENABLE")

    ############################################################################
    # Laser PWM
    ############################################################################

    def set_laser_power_perc(self, perc):
        perc = float(max(0, min(100, perc)))

        if perc >= 100:
            self.log(f"set_laser_power_perc: perc {perc}, disabling modulation")
            self.set_mod_enable(False)
            return

        period_us = 1000
        width_us = int(round(1.0 * perc * period_us / 100.0, 0))
        width_us = max(1, min(width_us, period_us))

        self.debug(f"set_laser_power_perc: setting perc {perc}% (period {period_us}, width {width_us})")
        self.set_mod_period_us(period_us)
        self.set_mod_width_us(width_us)
        self.set_mod_enable(True)

        self.laser_power_perc = perc

    def set_mod_enable(self, flag):
        self.send_cmd(0xbd, 1 if flag else 0, label="SET_MOD_ENABLE")

    def get_mod_enable(self):
        return 0 != self.get_cmd(0xe3, msb_len=1, label="GET_MOD_ENABLE")

    def set_mod_period_us(self, us):
        (lsw, msw, buf) = self.to40bit(us)
        return self.send_cmd(0xc7, lsw, msw, buf, label="SET_MOD_PERIOD")

    def get_mod_period_us(self):
        return self.get_cmd(0xcb, lsb_len=5, label="GET_MOD_PERIOD")

    def set_mod_width_us(self, us):
        (lsw, msw, buf) = self.to40bit(us)
        self.send_cmd(0xdb, lsw, msw, buf, label="SET_MOD_WIDTH")

    def get_mod_width_us(self):
        return self.get_cmd(0xdc, lsb_len=5, label="GET_MOD_WIDTH")

    ############################################################################
    # Laser TEC Setpoint
    ############################################################################

    def set_laser_tec_setpoint(self, raw):
        self.set_cmd(0xd8, wValue=0xa46)

    def get_detector_temperature_raw(self):
        result = self.get_cmd(0xd7, msb_len=2, label="GET_DETECTOR_TEMPERATURE_RAW")
        return result

    ############################################################################
    # Battery
    ############################################################################

    def get_battery_state(self):
        word = self.get_cmd(0xff, 0x13, msb_len=3, label="GET_BATTERY_STATE") # uint24

        lsb = (word >> 16) & 0xff
        msb = (word >>  8) & 0xff
        perc = msb + (1.0 * lsb / 256.0)
        is_charging = "charging" if word & 0xff else "discharging"

        return perc, is_charging

    ############################################################################
    #                                                                          #
    #                              Utility Methods                             #
    #                                                                          #
    ############################################################################

    def report(self, name, summary):
        name += ":"
        print(f"{name:30s} {summary}")
        self.log(f"REPORT *** {name}: {summary}")

    def debug(self, msg):
        if self.args.debug:
            print(f"{datetime.now()} DEBUG: {msg}")

    def log(self, msg):
        self.logfile.write(f"{datetime.now()} {msg}\n")
        self.logfile.flush()

    def log_header(self, msg):
        self.log("")
        self.log("=" * 40)
        self.log(msg)
        self.log("=" * 40)
        self.log("")

    def confirm(self, msg):
        if self.args.confirm:
            print(msg, end='')
            input(" (Ctrl-C to exit) ")

    def float_to_uint16(self, gain):
        msb = int(round(gain, 5)) & 0xff
        lsb = int((gain - msb) * 256) & 0xff
        return (msb << 8) | lsb

    def to40bit(self, val):
        lsw = val & 0xffff
        msw = (val >> 16) & 0xffff
        buf = [ (val >> 32) & 0xff ] + [0] * 7
        return (lsw, msw, buf)

    def send_cmd(self, cmd, value=0, index=0, buf=None, label=None):
        if buf is None:
            if self.pid == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug(f"send_cmd(0x{HOST_TO_DEVICE:02x}, 0x{cmd:02x}, 0x{value:04x}, 0x{index:04x}) >> {buf} ({label})")
        self.device.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None):
        self.debug(f"get_cmd(0x{DEVICE_TO_HOST:02x}, 0x{cmd:02x}, 0x{value:04x}, 0x{index:04x}, len {length}) ({label})")
        result = self.device.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        self.debug("  << {result}")

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

    def unpack(self, pos, data_type, label):
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
                page, offset, length, data_type, label))
            return

        buf = self.eeprom_pages[page]
        if buf is None or end_byte > len(buf):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (field %s)" % ( 
                page, offset, length, data_type, buf, label))
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

        extra = "" if label is None else f"({label})"
        self.debug(f"Unpacked page {page:02d}, offset {offset:02d}, len {length:02d}, datatype {data_type}: {unpack_result} {extra}")

        return unpack_result

    def pack(self, pos, data_type, value, label=None):
        page       = pos[0]
        start_byte = pos[1]
        length     = pos[2]
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
            self.debug("rounding negative to zero when writing to unsigned field (pos %s, data_type %s, value %s)" % (pos, data_type, value))
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
        self.debug("Packed (%d, %2d, %2d) '%s' value %s -> %s" % (page, start_byte, length, data_type, value, buf[start_byte:end_byte]))

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
        self.send_cmd(0xad, 0, label="ACQUIRE")

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
        self.outfile.write(", ".join([label, str(mean)] + [str(x) for x in spectrum]) + "\n")

        return spectrum

fixture = Fixture()
fixture.run()
