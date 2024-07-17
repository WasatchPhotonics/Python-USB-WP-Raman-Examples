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

import traceback
import usb.core
import argparse
import struct

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

# An extensible, stateful "Test Fixture" 
class Fixture(object):

    ############################################################################
    # Lifecycle 
    ############################################################################

    def __init__(self):
        self.eeprom_pages = None
        self.subformat = None
        self.last_acquire = datetime.now()

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--list",                action="store_true", help="list all spectrometers")
        parser.add_argument("--laser-enable",        action="store_true", help="enable laser during collection")
        parser.add_argument("--hardware-trigger",    action="store_true", help="enable triggering")
        parser.add_argument("--loop",                type=int,            help="repeat n times", default=1)
        parser.add_argument("--inner-loop",          type=int,            help="repeat n times", default=10)
        parser.add_argument("--delay-ms",            type=int,            help="delay n ms between spectra", default=0)
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms)")
        parser.add_argument("--integration-times",   type=str,            help="list of integration times (ms)")
        parser.add_argument("--outfile",             type=str,            help="outfile to save full spectra")
        parser.add_argument("--spectra",             type=int,            help="read the given number of spectra", default=0)
        parser.add_argument("--pixels",              type=int,            help="override pixel count")
        parser.add_argument("--continuous-count",    type=int,            help="how many spectra to read from a single ACQUIRE", default=1)
        parser.add_argument("--frame-id",            action="store_true", help="display internal frame ID for each spectrum")
        parser.add_argument("--set-dfu",             action="store_true", help="set matching spectrometers to DFU mode")
        parser.add_argument("--charging",            action=argparse.BooleanOptionalAction, help="configure battery charging")
        parser.add_argument("--reset-fpga",          action="store_true", help="reset FPGA")
        parser.add_argument("--serial-number",       type=str,            help="desired serial number")
        parser.add_argument("--model",               type=str,            help="desired model")
        parser.add_argument("--pid",                 type=str,            help="desired PID (e.g. 4000)")
        parser.add_argument("--eeprom-load-test",    action="store_true", help="load-test multiple EEPROMs")
        parser.add_argument("--dump",                action="store_true", help="dump basic getters")
        parser.add_argument("--fpga-options",        action="store_true", help="dump FPGA compilation options")
        parser.add_argument("--keep-trying",         action="store_true", help="ignore timeouts")
        parser.add_argument("--max-pages",           type=int,            help="number of EEPROM pages for load-test", default=8)
        self.args = parser.parse_args()

        if self.args.integration_times is None:
            if self.args.integration_time_ms is not None:
                self.args.integration_times = [ self.args.integration_time_ms ]
        else:
            self.args.integration_times = [ int(ms) for ms in self.args.integration_times.split(",") ]

        self.devices = []
        for pid in [0x1000, 0x2000, 0x4000]:
            if self.args.pid is not None:
                if pid != int(self.args.pid, 16):
                    continue
            self.devices.extend(usb.core.find(find_all=True, idVendor=0x24aa, idProduct=pid, backend=backend.get_backend()))

        for dev in self.devices:
            self.connect(dev)

        # read configuration
        for dev in self.devices:
            dev.fw_version = self.get_firmware_version(dev)
            #print(f"firmware version: {dev.fw_version}")

            dev.fpga_version = self.get_fpga_version(dev)
            #print(f"FPGA version: {dev.fpga_version}")

            self.read_eeprom(dev)
            dev.pixels = dev.eeprom["pixels"] if self.args.pixels is None else self.args.pixels

        # apply filters
        self.filter_by_serial()
        self.filter_by_model()

        if len(self.devices) == 0:
            print("No spectrometers found")

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

        # parse key fields (extend as needed)
        dev.eeprom = {}
        dev.eeprom["format"]        = self.unpack(dev, (0, 63,  1), "B")
        dev.eeprom["model"]         = self.unpack(dev, (0,  0, 16), "s")
        dev.eeprom["serial_number"] = self.unpack(dev, (0, 16, 16), "s")
        dev.eeprom["pixels"]        = self.unpack(dev, (2, 16,  2), "H")

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

        if self.args.continuous_count != 1:
            for dev in self.devices:
                # note we're leaving these set at exit
                self.set_continuous_frames(dev, self.args.continuous_count)
                self.set_continuous_acquisition(dev, True)

        if self.args.hardware_trigger:
            for dev in self.devices:
                self.set_trigger_source(dev, 1)

        # [self.get_fpga_configuration_register(dev) for dev in self.devices]

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

    def list(self):
        print("%-6s %-16s %-16s %3s %6s %-10s %-10s" % ("PID", "Model", "Serial", "Fmt", "Pixels", "FW", "FPGA"))
        for dev in self.devices:
            print("0x%04x %-16s %-16s %3d %6d %-10s %-10s" % (
                dev.idProduct, 
                dev.eeprom["model"], 
                dev.eeprom["serial_number"],
                dev.eeprom["format"],
                dev.pixels,
                dev.fw_version,
                dev.fpga_version))

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

    def reset_fpga(self, dev):
        print("resetting FPGA on %s" % dev.eeprom["serial_number"])
        self.send_cmd(dev, 0xb5)

    # only supported on Gen 1.5
    def get_fpga_configuration_register(self, dev):
        raw = self.get_cmd(dev, 0xb3, lsb_len=2, label="GET_FPGA_CONFIGURATION_REGISTER")
        self.debug(f"FPGA Configuration Register: 0x{raw:04x} ({label})")
        return raw

    def get_firmware_version(self, dev):
        result = self.get_cmd(dev, 0xc0)
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self, dev):
        s = ""
        result = self.get_cmd(dev, 0xb4, length=7)
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
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
        self.debug(f"setting triggerSource to {n}")
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

    def set_integration_time_ms(self, dev, n):
        if n < 1 or n > 0xffff:
            print("ERROR: script only supports positive uint16 integration time")
            return

        print("setting integrationTimeMS to %d" % n)
        self.send_cmd(dev, 0xb2, n)

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

    def do_acquisitions(self):
        outfile = open(self.args.outfile, 'w') if self.args.outfile is not None else None
        for i in range(self.args.spectra):
            for dev in self.devices:
                for j in range(self.args.continuous_count):
                    # send a software trigger on the FIRST of a continuous burst, unless hardware triggering enabled
                    send_trigger = (j == 0) and not self.args.hardware_trigger
                    spectrum = self.get_spectrum(dev, send_trigger)

                    now = datetime.now()
                    print("%s Spectrum %3d/%3d/%3d %s ..." % (now, j+1, i+1, self.args.spectra, spectrum[:10]))
                    if outfile is not None:
                        outfile.write("%s, %s\n" % (now, ", ".join([str(x) for x in spectrum])))

                    #if self.args.laser_enable:
                    #    self.get_laser_temperature(dev)

                    if self.args.frame_id:
                        self.get_frame_count(dev)

            self.debug(f"sleeping {self.args.delay_ms}ms")
            sleep(self.args.delay_ms / 1000.0 )

        if outfile is not None:
            outfile.close()

    def get_spectrum(self, dev, send_trigger=True):
        if send_trigger:
            return self.get_spectrum_sw_trigger(dev)
        else:
            return self.get_spectrum_hw_trigger(dev)

    def get_spectrum_sw_trigger(self, dev):
        if self.args.integration_time_ms:
            timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2
        else:
            timeout_ms = TIMEOUT_MS + 100 * 2

        print(f"{datetime.now()} sending trigger...")
        self.send_cmd(dev, 0xad, 0) # MZ: remind me, what was the '1' supposed to indicate?

        bytes_to_read = dev.pixels * 2
        block_size = 64
        data = []

        print(f"{datetime.now()} trying to read {dev.pixels} ({bytes_to_read} bytes) in chunks of {block_size} bytes")
        while True:
            try:
                self.debug(f"{datetime.now()} have {len(data)}/{bytes_to_read} bytes, reading next {block_size}")
                this_data = dev.read(0x82, block_size, timeout=timeout_ms)
                data.extend(this_data)
                if len(data) >= bytes_to_read:
                    break
            except usb.core.USBTimeoutError as ex:
                if not self.args.keep_trying:
                    raise 

        return self.demarshal_spectrum(data)

    def get_spectrum_hw_trigger(self, dev):
        now = datetime.now()
        print(f"{now} not sending trigger..", end='')  # note we don't send an ACQUIRE
        while True:
            try:
                print(".", end='')
                data = dev.read(0x82, dev.pixels * 2, timeout=1000)
                if data is not None:
                    ms_since_last = (now - self.last_acquire).total_seconds() * 1000.0
                    self.last_acquire = now

                    print()
                    print(f"{datetime.now()} received! ({ms_since_last:.2f}ms since last)")

                    return self.demarshal_spectrum(data)
            except Exception as ex:
                #print(ex)
                pass

    def demarshal_spectrum(self, data):
        spectrum = []
        if data is not None:
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

    def send_cmd(self, dev, cmd, value=0, index=0, buf=None):
        if buf is None:
            if dev.idProduct == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, dev, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None):
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d)" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS))
        result = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
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
