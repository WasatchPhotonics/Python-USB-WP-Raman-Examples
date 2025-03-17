"""
Attempt to reproduce QC dropouts observed when changing from long integration 
times to short ones.
"""

import argparse
import platform
import usb.core
import datetime
import numpy as np
import threading
import time
import os

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000

class Fixture:

    def __init__(self):
        self.dev = None

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",                       help="Verbose logging", action="store_true")
        parser.add_argument("--count",             type=int, help="How many spectra to collect at each integration time", default=5)
        parser.add_argument("--pixels",            type=int, help="pixels", default=1952)
        parser.add_argument("--loops",             type=int, help="how many times to change integration time", default=3)
        parser.add_argument("--start-integ-time",  type=int, help="first integration time (ms)", default=4000)
        parser.add_argument("--stop-integ-time",   type=int, help="second integration time (ms)", default=100)
        parser.add_argument("--sensor-timeout-ms", type=int, help="sensor timeout (ms)")
        self.args = parser.parse_args()

        # grab the first enumerated XS
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

    def report_sensor_timeout(self):
        ms = self.get_image_sensor_state_transition_timeout()
        print(f"\nimage sensor state transition timeout is 0x{ms:04x} ({ms}ms)")

    def run(self):

        # configure sensor timeout
        self.report_sensor_timeout()
        if self.args.sensor_timeout_ms is not None:
            print(f"changing to {self.args.sensor_timeout_ms}")
            self.set_image_sensor_state_transition_timeout(self.args.sensor_timeout_ms)
            self.report_sensor_timeout()

        bg = threading.Thread(target=self.bg_thread)
        bg.start()
        loops = 0
        while (loops < self.args.loops or self.args.loops == 0):
            print(f"\n=== Loop {loops+1} of {self.args.loops} ===")

            self.take_spectra(self.args.start_integ_time)
            self.take_spectra(self.args.stop_integ_time)

            loops += 1


    def bg_thread(self):
        while (True):
            print(f"checking adc")
            adc = self.get_adc_raw()
            print(f"checking battery")
            battery = self.get_battery_charge()
            print(f"adc raw {adc}; battery {battery}")
            time.sleep(1)

    def take_spectra(self, integ_time_ms):

        print(f"\nchanging integration time to {integ_time_ms}ms")
        self.set_integ_time(integ_time_ms)
        self.report_sensor_timeout()

        for i in range(self.args.count):

            start_time = datetime.datetime.now()
            print(f"{start_time} loop {i+1}/{self.args.count}...", end='')

            # take dark throwaway
            spectrum = self.get_spectrum()

            # print stats
            elapsed_ms = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
            print(f"took {elapsed_ms}ms at integ_time {integ_time_ms} yielding mean {spectrum.mean():.2f}, max {spectrum.max():.2f}")

    ############################################################################
    # opcodes
    ############################################################################

    def get_firmware_version(self):
        result = self.get_cmd(0xc0, label="GET_FIRMWARE_VERSION")
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self):
        s = ""
        result = self.get_cmd(0xb4, length=7, label="GET_FPGA_VERSION")
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
                    s += chr(c)
        return s

    def get_image_sensor_state_transition_timeout(self):
        return self.get_cmd(0xff, 0x72, lsb_len=2, label="GET_IMG_SNSR_STATE_TRANS_TIMEOUT")

    def get_battery_charge(self):
        return self.get_cmd(0xff, 0x13, lsb_len=3, label="GET_BATTERY_STATE")
        
    def get_adc_raw(self):
        return self.get_cmd(0xd5, msb_len=2, label="GET_ADC_RAW")

    def set_image_sensor_state_transition_timeout(self, ms):
        self.send_cmd(0xff, 0x71, ms, "SET_IMG_SNSR_STATE_TRANS_TIMEOUT")

    def set_integ_time(self, ms):
        self.send_cmd(0xb2, ms, label="SET_INTEG_TIME")
        self.integ_time = ms

    def get_spectrum(self):
        timeout_ms = TIMEOUT_MS + 2 * (self.args.start_integ_time + self.args.stop_integ_time)

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
