#!/usr/bin/env python

# We don't want this to become a copy of everything in Wasatch.PY, but we want to
# make certain things very easy and debuggable from the command-line

import platform
import math
import sys
import re
import os
from time import sleep
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

import traceback
import usb.core
import argparse
import struct

from EEPROMFields import parse_eeprom_pages

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

MAX_PAGES = 8
PAGE_SIZE = 64

# An extensible, stateful "Test Fixture" 
class Fixture(object):

    ############################################################################
    # Lifecycle 
    ############################################################################

    def __init__(self):
        self.eeprom_pages = None
        self.last_acquire = datetime.now()
        self.dev_by_sn = {}

        self.args = self.parse_args()

        self.devices = []
        for pid in [0x1000, 0x2000, 0x4000]:
            if self.args.pid is not None:
                if pid != int(self.args.pid, 16):
                    continue
            self.devices.extend(usb.core.find(find_all=True, idVendor=0x24aa, idProduct=pid, backend=backend.get_backend()))

        for dev in self.devices:
            self.connect(dev)

        # read settings for each unit
        for dev in self.devices:
            dev.fw_version = self.get_firmware_version(dev)
            dev.fpga_version = self.get_fpga_version(dev)

            if self.args.ble:
                dev.ble_version = self.get_ble_firmware_version(dev)

            self.read_eeprom(dev)

            dev.pixels = dev.eeprom["active_pixels_horizontal"] if self.args.pixels is None else self.args.pixels
            self.dev_by_sn[dev.eeprom["serial_number"]] = dev

        # apply filters
        self.filter_by_serial()
        self.filter_by_model()

        if len(self.devices) == 0:
            print("No spectrometers found")

        if self.args.integration_times is None:
            if self.args.integration_time_ms is not None:
                self.args.integration_times = [ self.args.integration_time_ms ]
        else:
            self.args.integration_times = [ int(ms) for ms in self.args.integration_times.split(",") ]


    def parse_args(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",               action="store_true", help="debug output")

        group = parser.add_argument_group("Connection")
        group.add_argument("--list",                action="store_true", help="list all spectrometers")
        group.add_argument("--ble",                 action="store_true", help="include BLE options")
        group.add_argument("--pid",                 type=str,            help="desired PID (e.g. 4000)")
        group.add_argument("--serial-number",       type=str,            help="desired serial number")
        group.add_argument("--model",               type=str,            help="desired model")
        group.add_argument("--pixels",              type=int,            help="override pixel count")
        group.add_argument("--set-dfu",             action="store_true", help="set matching spectrometers to DFU mode")
        group.add_argument("--keep-trying",         action="store_true", help="ignore timeouts")

        group = parser.add_argument_group("Acquisition Parameters")
        group.add_argument("--integration-time-ms", type=int,            help="integration time (ms)")
        group.add_argument("--integration-times",   type=str,            help="list of integration times (ms)")
        group.add_argument("--scans-to-average",    type=int,            help="set scan averaging (XS-only)")
        group.add_argument("--spectra",             type=int,            help="read the given number of spectra", default=0)
        group.add_argument("--delay-ms",            type=int,            help="delay n ms between spectra", default=0)
        group.add_argument("--continuous-count",    type=int,            help="how many spectra to read from a single ACQUIRE", default=1)
        group.add_argument("--loop",                type=int,            help="repeat n times", default=1)
        group.add_argument("--inner-loop",          type=int,            help="repeat n times", default=10)

        group = parser.add_argument_group("Auto-Raman")
        group.add_argument("--auto-raman",          action="store_true", help="use Auto-Raman measurments")
        for name, default in [ ("ar-max-ms",         20000),
                               ("ar-start-integ-ms",   100),
                               ("ar-start-gain-db",      0),
                               ("ar-max-integ-ms",    2000),
                               ("ar-min-integ-ms",      10),
                               ("ar-max-gain-db",       30),
                               ("ar-min-gain-db",        0),
                               ("ar-tgt-counts",     50000),
                               ("ar-max-counts",     55000),
                               ("ar-min-counts",     40000),
                               ("ar-max-factor",         5),
                               ("ar-saturation",     60000),
                               ("ar-max-avg",          125)]:
            group.add_argument(f"--{name}", type=int, default=default)
        group.add_argument(f"--ar-drop-factor", type=float, default=0.5)

        group = parser.add_argument_group("Post-Processing")
        group.add_argument("--bin-2x2",             action="store_true", help="apply 2x2 binning")
        group.add_argument("--plot",                action="store_true", help="graph spectra")
        group.add_argument("--overlay",             action="store_true", help="overlay graphed spectra")
        group.add_argument("--outfile",             type=str,            help="outfile to save full spectra")

        group = parser.add_argument_group("Testing")
        group.add_argument("--reset-fpga",          action="store_true", help="reset FPGA")
        group.add_argument("--laser-enable",        action="store_true", help="enable laser during collection")
        group.add_argument("--frame-id",            action="store_true", help="display internal frame ID for each spectrum")
        group.add_argument("--hardware-trigger",    action="store_true", help="enable triggering")
        group.add_argument("--laser-trigger-sn",    type=str,            help="serial number of the multi-channel unit whose laserEnable serves as group trigger")
        group.add_argument("--list-eeprom",         action="append",     help="list additional EEPROM fields")
        group.add_argument("--fpga-options",        action="store_true", help="dump FPGA compilation options")
        group.add_argument("--eeprom-load-test",    action="store_true", help="load-test multiple EEPROMs")
        group.add_argument("--dump",                action="store_true", help="dump basic getters")
        group.add_argument("--max-pages",           type=int,            help="number of EEPROM pages for load-test", default=8)
        group.add_argument("--monitor-battery",     action="store_true", help="monitor XS battery")
        group.add_argument("--charging",            action=argparse.BooleanOptionalAction, help="configure battery charging")
        group.add_argument("--shutdown",            action="store_true", help="turn off spectrometer")

        return parser.parse_args()

    def filter_by_serial(self):
        if self.args.serial_number is not None:
            filtered = []
            for dev in self.devices:
                if dev.eeprom["serial_number"].lower() == self.args.serial_number.lower():
                    filtered.append(dev)
            self.devices = filtered

    def filter_by_model(self):
        if self.args.model is not None:
            filtered = []
            for dev in self.devices:
                if dev.eeprom["model"].lower() == self.args.model.lower():
                    filtered.append(dev)
            self.devices = filtered

    def connect(self, dev):
        if os.name != "posix":
            self.debug("on Windows, so NOT setting configuration and claiming interface")
        elif "macOS" in platform.platform():
            self.debug("on MacOS, so NOT setting configuration and claiming interface")
        else:
            self.debug("on Linux, so setting configuration and claiming interface")
            dev.set_configuration(1)
            usb.util.claim_interface(dev, 0)
            self.debug("claimed device")

    def read_eeprom(self, dev):
        dev.buffers = [self.get_cmd(dev, 0xff, 0x01, page) for page in range(8)]
        dev.eeprom = parse_eeprom_pages(dev.buffers)

        # save each page as hex string
        dev.eeprom["hexdump"] = {}
        for i, buf in enumerate(dev.buffers):
            dev.eeprom["hexdump"][i] = " ".join([f"{v:02x}" for v in buf])

    ############################################################################
    # Commands
    ############################################################################

    def run(self):
        if len(self.devices) > 0:
            dev = self.devices[0]

        if self.args.list:
            self.list()

        if self.args.dump:
            self.dump()

        if self.args.fpga_options:
            for dev in self.devices:
                self.dump_fpga_options(dev)

        if self.args.set_dfu:
            for dev in self.devices:
                self.set_dfu(dev)
            return

        if self.args.charging is not None:
            for dev in self.devices:
                self.set_charging(dev, self.args.charging)

        if self.args.reset_fpga:
            for dev in self.devices:
                self.reset_fpga(dev)
            return

        if self.args.shutdown:
            for dev in self.devices:
                self.shutdown(dev)
            return

        if self.args.continuous_count != 1:
            for dev in self.devices:
                # note we're leaving these set at exit
                self.set_continuous_frames(dev, self.args.continuous_count)
                self.set_continuous_acquisition(dev, True)

        if self.args.hardware_trigger:
            for dev in self.devices:
                self.set_trigger_source(dev, 1)

        # [self.get_fpga_configuration_register(dev) for dev in self.devices]

        if self.args.scans_to_average:
            n = self.args.scans_to_average
            for dev in self.devices:
                self.set_scans_to_average(dev, n)
                check = self.get_scans_to_average(dev)
                if check != n:
                    print(f"WARNING: failed to set {n} scan averaging (read {check})")

        if self.args.laser_enable:
            [self.set_laser_enable(dev, 1) for dev in self.devices]

        if self.args.integration_times is None:
            self.do_acquisitions()
        else:
            for ms in self.args.integration_times:
                self.args.integration_time_ms = ms
                for dev in self.devices:
                    self.set_integration_time_ms(dev, self.args.integration_time_ms)
                self.do_acquisitions()

        if self.args.eeprom_load_test:
            self.do_eeprom_load_test()

        # disable laser on shutdown
        if self.args.laser_enable:
            [self.set_laser_enable(dev, 0) for dev in self.devices]

        # reset trigger source on shutdown
        if self.args.hardware_trigger:
            [self.set_trigger_source(dev, 0) for dev in self.devices]

        if self.args.monitor_battery:
            while True:
                for dev in self.devices:
                    (raw, percentage, charging) = self.get_battery_level(dev)
                    print(f"{datetime.now()} battery {percentage:5.2f}% {raw} {'charging' if charging else 'NOT charging'}")
                sleep(1)

        if self.args.plot and self.args.spectra:
            print("Press return to exit...", end='')
            foo = input()

    def list(self):
        header = "%-6s %-16s %-16s %3s %6s %-10s %-10s" % ("PID", "Model", "Serial", "Fmt", "Pixels", "FW", "FPGA")
        if self.args.ble:
            header += "%-10s" % "BLE"
        if self.args.list_eeprom:
            for foo in self.args.list_eeprom:
                header += "%-10s" % foo
        print(header)
        for dev in self.devices:
            row = "0x%04x %-16s %-16s %3d %6d %-10s %-10s" % (
                dev.idProduct, 
                dev.eeprom["model"], 
                dev.eeprom["serial_number"],
                dev.eeprom["format"],
                dev.pixels,
                dev.fw_version,
                dev.fpga_version)
            if self.args.ble:
                row += "%-10s" % dev.ble_version
            if self.args.list_eeprom:
                for foo in self.args.list_eeprom:
                    if foo in dev.eeprom:
                        row += "%-10s" % dev.eeprom[foo]
            print(row)

    def dump(self):
        # consider adding more later...will need more logic regarding msb, datatype etc
        getters = {
            "GET_INTEGRATION_TIME_MS": { "opcode": 0xbf, "lsb_len": 3 }
        }

        for dev in self.devices:
            print(f"{dev.eeprom['model']} {dev.eeprom['serial_number']}")
            for name in getters:
                value = self.get_cmd(dev, getters[name]["opcode"], lsb_len=getters[name]["lsb_len"], label=name)
                print(f"  {name:32s} 0x{value:04x} {value}")
                
    ############################################################################
    # opcodes
    ############################################################################

    def get_battery_level(self, dev):
        raw = self.get_cmd(dev, 0xff, 0x13, length=3)
        percentage = raw[1] + (1.0 * raw[0] / 256.0)
        charging = raw[2] != 0
        return (raw, percentage, charging)

    def reset_fpga(self, dev):
        print("resetting FPGA on %s" % dev.eeprom["serial_number"])
        self.send_cmd(dev, 0xb5)

    def shutdown(self, dev):
        print("shutting down %s" % dev.eeprom["serial_number"])
        self.send_cmd(dev, 0x87)
        print("%s has been shutdown" % dev.eeprom["serial_number"])

    # only supported on Gen 1.5
    def get_fpga_configuration_register(self, dev):
        raw = self.get_cmd(dev, 0xb3, lsb_len=2, label="GET_FPGA_CONFIGURATION_REGISTER")
        self.debug(f"FPGA Configuration Register: 0x{raw:04x} ({label})")
        return raw

    def get_firmware_version(self, dev):
        result = self.get_cmd(dev, 0xc0, label="GET_FIRMWARE_VERSION")
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self, dev):
        s = ""
        result = self.get_cmd(dev, 0xb4, length=7, label="GET_FPGA_VERSION")
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
                    s += chr(c)
        return s

    def get_ble_firmware_version(self, dev):
        # note: it takes a few seconds after boot before this returns a reasonable value
        result = self.get_cmd(dev, 0xff, 0x2d, length=32, label="GET_BLE_FIRMWARE_VERSION")
        if result is None:
            return None

        s = ""
        for c in result:
            if c == 0:
                break
            s += chr(c)
        return s

    def set_dfu(self, dev):
        print("setting DFU on %s" % dev.eeprom["serial_number"])
        self.send_cmd(dev, 0xfe)

    def set_charging(self, dev, flag):
        print(f"setting charging to {flag} on {dev.eeprom['serial_number']}")
        self.send_cmd(dev, 0x86, 1 if flag else 0)

    def set_laser_enable(self, dev, flag):
        self.debug("setting laserEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(dev, 0xbe, 1 if flag else 0)

    def set_trigger_source(self, dev, n):
        sn = dev.eeprom["serial_number"]
        self.debug(f"setting triggerSource to {n} on {sn}")
        self.send_cmd(dev, 0xd2, n)

    def set_continuous_acquisition(self, dev, flag):
        self.debug(f"setting continuous acquisition to {flag}")
        self.send_cmd(dev, 0xc8, 1 if flag else 0)

    def set_continuous_frames(self, dev, n):
        self.debug(f"setting continuous frame count to {n}")
        self.send_cmd(dev, 0xc9, n)

    def set_selected_laser(self, dev, n):
        if n < 0 or n > 0xffff:
            print("ERROR: selectedLaser requires uint16")
            return

        print("setting selectedLaser to %d" % n)
        self.send_cmd(dev, 0xff, 0x15, n)

    def set_selected_adc(self, dev, n):
        if not n in (0, 1):
            print("ERROR: selectedADC requires 0 or 1")
            return

        print("setting selectedADC to %d" % n)
        self.send_cmd(dev, 0xed, n)

    def set_scans_to_average(self, dev, n):
        if dev.idProduct != 0x4000:
            return
        self.send_cmd(dev, 0xff, 0x62, n)

    def set_integration_time_ms(self, dev, n):
        if n < 1 or n > 0xffff:
            print("ERROR: script only supports positive uint16 integration time")
            return

        sn = dev.eeprom["serial_number"]
        print(f"{datetime.now()} setting integrationTimeMS to {n} on {sn}")
        self.send_cmd(dev, 0xb2, n)

    def get_integration_time_ms(self, dev):
        return self.get_cmd(dev, 0xbf, lsb_len=3)

    def get_detector_gain(self, dev):
        result = self.get_cmd(dev, 0xc5)
        lsb = result[0]
        msb = result[1]
        return msb + lsb / 256.0

    def get_scans_to_average(self, dev):
        return self.get_cmd(dev, 0xff, 0x63, lsb_len=2)

    def set_modulation_enable(self, dev, flag):
        print("setting laserModulationEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(dev, 0xbd, 1 if flag else 0)

    def set_raman_mode(self, dev, flag):
        print("setting Raman Mode %s" % ("on" if flag else "off"))
        self.send_cmd(dev, 0xff, 0x16, 1 if flag else 0)

    def set_raman_delay_ms(self, dev, ms):
        if ms < 0 or ms > 0xffff:
            print("ERROR: raman delay requires uint16")
            return

        print("setting Raman Delay %d ms" % ms)
        self.send_cmd(dev, 0xff, 0x20, ms)

    def set_watchdog_sec(self, dev, sec):
        if sec < 0 or sec > 0xffff:
            print("ERROR: watchdog requires uint16")
            return

        print("setting Raman Watchdog %d sec" % sec)
        self.send_cmd(dev, 0xff, 0x18, sec)

    def get_laser_temperature(self, dev):
        raw = self.get_cmd(dev, 0xd5, lsb_len=2)

        voltage    = 2.5 * raw / 4096
        resistance = 21450.0 * voltage / (2.5 - voltage) 

        if resistance < 0:
            print(f"can't compute degC: raw = 0x{raw:04x}, voltage = {voltage}, resistance = {resistance}")
            return

        logVal     = math.log(resistance / 10000.0)
        insideMain = logVal + 3977.0 / (25 + 273.0)
        degC       = 3977.0 / insideMain - 273.0
        print(f"laser temperature = {degC:.2f} C")

    def get_frame_count(self, dev):
        count = self.get_cmd(dev, 0xe4, lsb_len=2)
        print(f"frame count = {count} (0x{count:04x})")

    def dump_fpga_options(self, dev):
        word = self.get_cmd(dev, 0xff, 0x04, label="READ_COMPILATION_OPTIONS", lsb_len=2)

        opts = {}
        opts["integration_time_resolution"] = (word & 0x0007)
        opts["data_header"]                 = (word & 0x0038) >> 3
        opts["has_cf_select"]               = (word & 0x0040) != 0
        opts["laser_type"]                  = (word & 0x0180) >> 7
        opts["laser_control"]               = (word & 0x0e00) >> 9
        opts["has_area_scan"]               = (word & 0x1000) != 0
        opts["has_actual_integ_time"]       = (word & 0x2000) != 0
        opts["has_horiz_binning"]           = (word & 0x4000) != 0

        print(f"FPGA Compilation Options: 0x{word:04x}")
        for k, v in opts.items():
            print(f"  {k} = {v}")

    def do_eeprom_load_test(self):
        """
        When validating a new source of EEPROM chips, or FX2 FW responsible for 
        reading same, it can be useful to "hammer" the EEPROM on one or more 
        connected units with a rapid series of read tests.
        """
        def make_key(dev):
            return f"0x{dev.idVendor:04x}:0x{dev.idProduct:04x}:0x{dev.address:04x}:{dev.eeprom['serial_number']}"

        filename = f"eeprom-load-test-{datetime.now().strftime('%Y%m%d')}.log"
        with open(filename, 'a') as out:

            # write file header
            out.write("EEPROM Load Test Starting\n")
            for dev in self.devices:
                out.write(f"{make_key(dev)} initial EEPROM:\n")
                for i, s in dev.eeprom["hexdump"].items():
                    out.write(f"  {i}: {s}\n")

            msg = f"Each of the following {self.args.loop} iterations will read {self.args.max_pages} pages " \
                 +f"{self.args.inner_loop} times consecutively over {len(self.devices)} spectrometers with\n" \
                 +f"{self.args.delay_ms}ms delay between reads " \
                 +f"({self.args.loop * self.args.max_pages * self.args.inner_loop * len(self.devices)} " \
                 +f"total page reads)"
            out.write(f"{msg}\n")
            print(msg)

            print("load test iterations...", end='')
            failures = {}
            try:
                for count in range(self.args.loop):
                    print(".", end='', flush=True)

                    for dev in self.devices:
                        key = f"0x{dev.idVendor:04x}:0x{dev.idProduct:04x}:0x{dev.address:04x}:{dev.eeprom['serial_number']}"
                        # test same spectrometer several times in a row
                        for inner in range(self.args.inner_loop):

                            if key not in failures:
                                failures[key] = 0

                            # read all 8 pages
                            ee = [self.get_cmd(dev, 0xff, 0x01, page) for page in range(self.args.max_pages)]
                            ss = {}
                            for i, buf in enumerate(ee):
                                ss[i] = " ".join([f"{v:02x}" for v in buf])

                            # the following sequence of 63 bytes is of engineering interest
                            # if it appears anywhere within a 64-byte EEPROM page
                            IMMUTABLE = r"c2 47 05 31 21 00 00 04 00 03 00 00 02 31 a5 00 " \
                                      +  "03 00 33 02 39 0f 00 03 00 43 02 2f 00 00 03 00 " \
                                      +  "4b 02 2b 23 00 03 00 53 02 2f 00 03 ff 01 00 90 " \
                                      +  "e6 78 e0 54 10 ff c4 54 0f 44 50 f5 09 13 e4"

                            passed = True
                            for i, s in ss.items():
                                orig = dev.eeprom["hexdump"][i]
                                if re.search(IMMUTABLE, s):
                                    print(f"\n    {key} failure on loop {count}: page {i} matches immutable")
                                    passed = False
                                elif s != orig:
                                    print(f"\n    {key} failure on loop {count}: page {i} differed from original")
                                    print(f"        read: {s}")
                                    print(f"        orig: {orig}")
                                    passed = False
                                else:
                                    pass

                            if not passed:
                                failures[key] += 1

                            out.write(f"{datetime.now()}, {key}, {passed}\n")
            except usb.core.USBError as ex:
                out.write(f"{datetime.now()}, {key}, False: {ex}\n")

        print("\nEEPROM Load Test report:")
        for key in failures:
            print(f"  {key} had {failures[key]} failures")

    def pulse_laser_trigger(self):
        sn = self.args.laser_trigger_sn
        if sn:
            dev = self.dev_by_sn.get(self.args.laser_trigger_sn, None)
            if dev:
                print(f"\n{datetime.now()} pulsing laser on {sn}")
                self.set_laser_enable(dev, True)
                sleep(0.005)
                self.set_laser_enable(dev, False)

    def do_acquisitions(self):
        if self.args.outfile:
            outfile = open(self.args.outfile, 'w') 
            # tricky to write wavelengths / wavenumbers here, since technically we support multiple devices...
        else:
            outfile = None

        if self.args.plot:
            plt.ion()

        spectra = []
        for i in range(self.args.spectra):

            if self.args.laser_trigger_sn:
                self.pulse_laser_trigger()

            start = None
            for dev in self.devices:
                for j in range(self.args.continuous_count):
                    # send a software trigger on the FIRST of a continuous burst, unless hardware triggering enabled
                    send_trigger = (j == 0) and not self.args.hardware_trigger
                    acq_type = 3 if self.args.auto_raman else 0
                    spectrum = self.get_spectrum(dev, send_trigger, acq_type)

                    now = datetime.now()
                    if not start:
                        start = now
                    print("%s Spectrum %3d/%3d/%3d %s ..." % (now, j+1, i+1, self.args.spectra, spectrum[:10]))
                    spectra.append(spectrum)
                    if outfile is not None:
                        outfile.write("%s, %s\n" % (now, ", ".join([str(x) for x in spectrum])))

                    #if self.args.laser_enable:
                    #    self.get_laser_temperature(dev)

                    if self.args.frame_id:
                        self.get_frame_count(dev)

                    if self.args.plot:
                        if not self.args.overlay:
                            plt.clf()
                        plt.plot(spectrum)
                        plt.draw()
                        plt.pause(0.01)

            if len(self.devices) > 1:
                print(f"All spectra received within {(datetime.now() - start).total_seconds() * 1000:.2f}ms (first to last)")
            self.debug(f"sleeping {self.args.delay_ms}ms")
            sleep(self.args.delay_ms / 1000.0 )

        if len(spectra):
            stdevs = []
            for px in range(len(spectra[0])):
                values = []
                for t in range(len(spectra)):
                    values.append(spectra[t][px])
                stdevs.append(np.std(values))
            avg_std = sum(stdevs) / len(stdevs)
            print(f"Mean pixel stdev over {len(spectra)} spectra: {avg_std:.2f}")

        if outfile is not None:
            outfile.close()

    def get_spectrum(self, dev, send_trigger=True, acq_type=0):
        if send_trigger:
            spectrum = self.get_spectrum_sw_trigger(dev, acq_type)
        else:
            spectrum = self.get_spectrum_hw_trigger(dev)

        if dev.idProduct == 0x4000:
            for i in range(4):
                spectrum[i] = spectrum[4]

        if self.args.bin_2x2:
            # note, this needs updated for 633XS
            binned = []
            for i in range(len(spectrum)-1):
                binned.append((spectrum[i] + spectrum[i+1]) / 2.0)
            binned.append(spectrum[-1])
            spectrum = binned
        
        return spectrum

    def get_spectrum_sw_trigger(self, dev, acq_type=0):
        sn = dev.eeprom["serial_number"]
        num_dev = len(self.devices)
        if self.args.integration_time_ms:
            if self.args.scans_to_average:
                timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * (self.args.scans_to_average + 1) + 500 * num_dev
            else:
                timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2 + 1000 * num_dev
        else:
            timeout_ms = TIMEOUT_MS + 100 * 2

        if acq_type == 3:
            print(f"{datetime.now()} requesting Auto-Raman measurement...")
            self.test_auto_raman(dev)
        else:
            print(f"{datetime.now()} sending trigger to {sn}...")
            self.send_cmd(dev, 0xad, acq_type)

        bytes_to_read = dev.pixels * 2
        block_size = 64
        block_size = bytes_to_read # testing multi-channel
        data = []

        print(f"{datetime.now()} trying to read {dev.pixels} ({bytes_to_read} bytes) in chunks of {block_size} bytes with timeout {timeout_ms}ms from {sn}")
        while True:
            try:
                self.debug(f"{datetime.now()} have {len(data)}/{bytes_to_read} bytes, reading next {block_size}")
                this_data = dev.read(0x82, block_size, timeout=timeout_ms)
                data.extend(this_data)
                if len(data) >= bytes_to_read:
                    break
            except usb.core.USBTimeoutError as ex:
                if not (self.args.keep_trying or self.args.auto_raman):
                    raise 

        if acq_type == 3:
            final_integ_ms = self.get_integration_time_ms(dev)
            final_gain_db  = self.get_detector_gain(dev)
            final_scan_avg = self.get_scans_to_average(dev)
            print(f"Integration Time {final_integ_ms}ms, Gain {final_gain_db}dB, Avg {final_scan_avg} scans")

        return self.demarshal_spectrum(data)

    def get_spectrum_hw_trigger(self, dev):
        sn = dev.eeprom["serial_number"]
        print(f"{datetime.now()} waiting for trigger on {sn}...", end='')  # don't send an ACQUIRE
        while True:
            try:
                print(".", end='')
                data = dev.read(0x82, dev.pixels * 2, timeout=1000) # timeout doesn't really matter, because we're in a loop that ignores timeouts
                if data is not None:
                    now = datetime.now()
                    ms_since_last = (now - self.last_acquire).total_seconds() * 1000.0
                    self.last_acquire = now

                    print(f"received ({ms_since_last:.2f}ms since last)")
                    return self.demarshal_spectrum(data)

            except usb.core.USBTimeoutError as ex:
                pass

    def demarshal_spectrum(self, data):
        spectrum = []
        if data is not None:
            for i in range(0, len(data), 2):
                spectrum.append(data[i] | (data[i+1] << 8))
        return spectrum

    ############################################################################
    # Firmware Auto-Raman (USB)
    ############################################################################

    # compare to wasatch.AutoRamanRequest
    def test_auto_raman(self, dev):
        buf = []
        buf.extend([self.args.ar_max_ms           & 0xff, (self.args.ar_max_ms        >> 8) & 0xff])
        buf.extend([self.args.ar_start_integ_ms   & 0xff, (self.args.ar_start_integ_ms>> 8) & 0xff])
        buf.extend([self.args.ar_start_gain_db    & 0xff                                             ])
        buf.extend([self.args.ar_max_integ_ms     & 0xff, (self.args.ar_max_integ_ms  >> 8) & 0xff])
        buf.extend([self.args.ar_min_integ_ms     & 0xff, (self.args.ar_min_integ_ms  >> 8) & 0xff])
        buf.extend([self.args.ar_max_gain_db      & 0xff                                             ])
        buf.extend([self.args.ar_min_gain_db      & 0xff                                             ])
        buf.extend([self.args.ar_tgt_counts       & 0xff, (self.args.ar_tgt_counts    >> 8) & 0xff])
        buf.extend([self.args.ar_max_counts       & 0xff, (self.args.ar_max_counts    >> 8) & 0xff])
        buf.extend([self.args.ar_min_counts       & 0xff, (self.args.ar_min_counts    >> 8) & 0xff])
        buf.extend([self.args.ar_max_factor       & 0xff                                             ])
        buf.extend([int(self.args.ar_drop_factor) & 0xff, int((self.args.ar_drop_factor - int(self.args.ar_drop_factor)) * 256)])
        buf.extend([self.args.ar_saturation       & 0xff, (self.args.ar_saturation    >> 8) & 0xff])
        buf.extend([self.args.ar_max_avg          & 0xff                                             ]) 

        print(f"params len {len(buf)}: {self.to_hex(buf)}")
        for name, value in vars(self.args).items():
            if name.startswith("ar_"):
                print(f"  {name:17s} {str(value):8s} " + ("" if name == "ar_drop_factor" else f"0x{value:04x}"))

        self.send_cmd(dev, 0xfd, 0, 0, buf)
        print(f"back from sending params")

    def to_hex(self, a):
        return "[ " + ", ".join([f"{v:02x}" for v in a]) + " ]"

    ############################################################################
    # Utility Methods
    ############################################################################

    def str2bool(self, s):
        return s.lower() in ("true", "yes", "on", "enable", "1")

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, dev, cmd, value=0, index=0, buf=None):
        if buf is None:
            if dev.idProduct == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, dev, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None):
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, label))
        result = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) << %s %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, self.to_hex(result), label))

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

    def unpack(self, dev, address, data_type):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        buf = dev.buffers[page]
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
if len(fixture.devices) > 0:
    fixture.run()
