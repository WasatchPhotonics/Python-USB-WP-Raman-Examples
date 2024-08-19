"""
A short script that collects 200 of dark-corrected spectra back to back of a 
single sample with random laser powers, integration times, and gains (say, 
between 100 ms and 2000 ms, 5% to 100% laser power, and between 8 dB and 32 dB) 
with a comparable SIG? Just read the dark and signal spectra for each setting 
and, say, just print out the settings and the dark corrected intensity of pixel 
number 1000 or something else that is quick and easy.
"""

import argparse
import platform
import usb.core
import datetime
import numpy as np
import os

from random import randrange

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

class Fixture:

    def __init__(self):
        self.dev = None
        self.integ_time = 100
        self.last_integ_time = 100

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",                    help="Verbose logging", action="store_true")
        parser.add_argument("--count",          type=int, help="How many spectra to collect", default=5)
        parser.add_argument("--min-integ-time", type=int, help="Lowest random integration time (ms)", default=100)
        parser.add_argument("--max-integ-time", type=int, help="Highest random integration time (ms)", default=2000)
        parser.add_argument("--min-gain-db",    type=int, help="Lowest random gain (dB)", default=8)
        parser.add_argument("--max-gain-db",    type=int, help="Highest random gain (dB)", default=32)
        parser.add_argument("--min-laser-perc", type=int, help="Lowest random laser power (%%)", default=5)
        parser.add_argument("--max-laser-perc", type=int, help="Highest random laser power (%%)", default=100)
        parser.add_argument("--output-pixel",   type=int, help="Pixel value to output", default=1000)
        parser.add_argument("--pixels",         type=int, help="Pixels to read", default=1952)
        parser.add_argument("--outfile",        type=str, help="File to hold row-ordered CSV output")
        self.args = parser.parse_args()

        for dev in usb.core.find(find_all=True, idVendor=0x24aa, idProduct=0x4000, backend=backend.get_backend()):
            self.dev = dev
            break
        if self.dev is None:
            print("No spectrometer found.")
            return

        # connect
        if os.name != "posix":
            self.debug("on Windows, so NOT setting configuration and claiming interface")
        elif "macOS" in platform.platform():
            self.debug("on MacOS, so NOT setting configuration and claiming interface")
        else:
            self.debug("on Linux, so setting configuration and claiming interface")
            self.dev.set_configuration(1)
            usb.util.claim_interface(self.dev, 0)

        # read configuration
        fw_version = self.get_firmware_version()
        fpga_version = self.get_fpga_version()
        print(f"connected to spectrometer with FW {fw_version} and FPGA {fpga_version}")

    def run(self):

        # disable laser warning delay (allow laser to fire as soon as enabled)
        self.set_laser_warning_delay(0)

        # extend the sensor timeout
        self.set_sensor_timeout(0xffff)

        # no need to configure laser TEC setpoint -- that's done in firmware by reading the EEPROM

        if self.args.outfile:
            with open(self.args.outfile, "a") as outfile:
                outfile.write(f"time,loop,type,spectrum\n")

        for i in range(1, self.args.count + 1):

            # remember last integration time
            self.last_integ_time = self.integ_time

            # randomize settings
            integ_time = randrange(self.args.min_integ_time, self.args.max_integ_time)
            gain_db = round(randrange(self.args.min_gain_db * 10, self.args.max_gain_db * 10) / 10.0, 1)
            laser_perc = randrange(self.args.min_laser_perc, self.args.max_laser_perc)

            # print(f"{datetime.datetime.now()} loop {i:3d}/{self.args.count:3d}: " +
            #       f"integ_time {integ_time:4d}, gain {gain_db:4.1f}dB, laser {laser_perc:3d}% [setting]")

            # apply settings
            self.set_integ_time(integ_time)
            self.set_gain(gain_db)
            self.set_laser_power_perc(laser_perc)

            # disable laser
            self.set_laser_enable(False)

            # take dark throwaway
            self.get_spectrum()

            # take dark
            dark = self.get_spectrum()

            # enable laser
            self.set_laser_enable(True)
            
            # take sample throwaway
            self.get_spectrum()

            # take Raman sample
            sample = self.get_spectrum()

            # perform dark correction
            corr = sample - dark

            # compute stats
            max_dark    = dark.max()
            max_sample  = sample.max()
            max_corr    = corr.max()
            mean_dark   = dark.mean()
            mean_sample = sample.mean()
            mean_corr   = corr.mean()
            at_pixel    = corr[self.args.output_pixel]

            # print stats
            now = datetime.datetime.now()
            print(f"{now} loop {i:3d}/{self.args.count:3d}: " +
                  f"integ_time {integ_time:4d}, gain {gain_db:4.1f}dB, laser {laser_perc:3d}%, " +
                  f"max_dark {max_dark:8.2f}, max_sample {max_sample:8.2f}, max_corr {max_corr:8.2f}, " + 
                  f"mean_dark {mean_dark:8.2f}, mean_sample {mean_sample:8.2f}, mean_corr {mean_corr:8.2f}, " +
                  f"at pixel {self.args.output_pixel} {at_pixel:8.2f}")

            # save data
            if self.args.outfile:
                with open(self.args.outfile, "a") as outfile:
                    outfile.write(f"{now},{i},dark,"   + ",".join([f"{x:.2f}" for x in dark])   + "\n")
                    outfile.write(f"{now},{i},sample," + ",".join([f"{x:.2f}" for x in sample]) + "\n")
                    outfile.write(f"{now},{i},corr,"   + ",".join([f"{x:.2f}" for x in corr])   + "\n")

    ############################################################################
    # opcodes
    ############################################################################

    def get_firmware_version(self):
        result = self.get_cmd(0xc0, label="GET_FIRMWARE_VERSION")
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

    def set_laser_warning_delay(self, sec):
        self.send_cmd(0x8a, sec, label="SET_LASER_WARNING_DELAY")

    def set_sensor_timeout(self, ms):
        self.send_cmd(0xff, 0x71, ms, "SET_IMG_SNSR_STATE_TRANS_TIMEOUT")

    def set_integ_time(self, ms):
        self.send_cmd(0xb2, ms, label="SET_INTEG_TIME")
        self.integ_time = ms

    def set_gain(self, gain):
        raw = self.float_to_uint16(gain)
        result = self.send_cmd(0xb7, raw, label="SET_GAIN")

    def set_laser_enable(self, flag):
        self.send_cmd(0xbe, 1 if flag else 0, label="SET_LASER_ENABLE")

    def set_mod_enable(self, flag):
        self.send_cmd(0xbd, 1 if flag else 0, label="SET_MOD_ENABLE")

    def set_laser_power_perc(self, perc):
        if perc <= 0:
            return self.set_laser_enable(False)

        if perc >= 100:
            self.set_mod_enable(False)
            return self.set_laser_enable(True)

        self.send_cmd(0xc7, 1000, label="SET_MOD_PERIOD") # period_us
        self.send_cmd(0xdb, perc * 10, label="SET_MOD_WIDTH") 
        self.set_mod_enable(True)

    def get_spectrum(self):
        timeout_ms = TIMEOUT_MS + 2 * (self.last_integ_time + self.integ_time)

        self.send_cmd(0xad, 0) # SW trigger

        bytes_to_read = self.args.pixels * 2
        data = self.dev.read(0x82, bytes_to_read, timeout=timeout_ms)

        spectrum = []
        for i in range(0, len(data), 2):
            spectrum.append(data[i] | (data[i+1] << 8))
        return np.array(spectrum, dtype=np.float32)

    ############################################################################
    # utility
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print(f"DEBUG: {msg}")

    def float_to_uint16(self, gain):
        msb = int(round(gain, 5)) & 0xff
        lsb = int((gain - msb) * 256) & 0xff
        return (msb << 8) | lsb

    def send_cmd(self, cmd, value=0, index=0, buf=None, label=None):
        if buf is None:
            if self.dev.idProduct == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug(f"ctrl_transfer(0x{HOST_TO_DEVICE:02x}, 0x{cmd:02x}, 0x{value:04x}, 0x{index:04x}) {label if label else ''}")
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None):
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
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

fixture = Fixture()
if fixture.dev:
    fixture.run()
