#!/usr/bin/env python

# We don't want this to become a copy of everything in Wasatch.PY, but we want to
# make certain things very easy and debuggable from the command-line

import math
import sys
import re
from time import sleep
from datetime import datetime

import traceback
import usb.core
import argparse
import struct
import sys

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

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--list",                action="store_true", help="list all spectrometers")
        parser.add_argument("--laser-enable",        action="store_true", help="enable laser during collection")
        parser.add_argument("--trigger-enable",      action="store_true", help="enable triggering")
        parser.add_argument("--loop",                type=int,            help="repeat n times", default=1)
        parser.add_argument("--delay-ms",            type=int,            help="delay n ms between spectra", default=10)
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms)", default=100)
        parser.add_argument("--outfile",             type=str,            help="outfile to save full spectra")
        parser.add_argument("--spectra",             type=int,            help="read the given number of spectra", default=0)
        parser.add_argument("--set-dfu",             action="store_true", help="set matching spectrometers to DFU mode")
        parser.add_argument("--reset-fpga",          action="store_true", help="reset FPGA")
        parser.add_argument("--serial-number",       type=str,            help="desired serial number")
        parser.add_argument("--model",               type=str,            help="desired model")
        parser.add_argument("--pid",                 type=str,            help="desired PID (e.g. 4000)")
        self.args = parser.parse_args()

        self.devices = []
        for pid in [0x1000, 0x2000, 0x4000]:
            if self.args.pid is not None:
                if pid != int(self.args.pid, 16):
                    continue
            self.devices.extend(usb.core.find(find_all=True, idVendor=0x24aa, idProduct=pid))

        # is this needed?
        for dev in self.devices:
            self.connect(dev)

        # read configuration
        for count in range(self.args.loop):
            print(f"loop {count}")
            for dev in self.devices:
                dev.fw_version = self.get_firmware_version(dev)
                print(f"firmware version: {dev.fw_version}")

                dev.fpga_version = self.get_fpga_version(dev)
                print(f"FPGA version: {dev.fpga_version}")

                self.read_eeprom(dev)

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

    ############################################################################
    # Commands
    ############################################################################

    def run(self):
        if len(self.devices) > 0:
            dev = self.devices[0]

        if self.args.list:
            self.list()

        if self.args.set_dfu:
            for dev in self.devices:
                self.set_dfu(dev)
            return

        if self.args.reset_fpga:
            for dev in self.devices:
                self.reset_fpga(dev)
            return

        if self.args.integration_time_ms is not None:
            for dev in self.devices:
                self.set_integration_time_ms(dev, self.args.integration_time_ms)

        if self.args.trigger_enable:
            [self.set_continuous_frames     (dev, 1) for dev in self.devices]
            [self.set_continuous_acquisition(dev, 0) for dev in self.devices]
            [self.set_trigger_source        (dev, 1) for dev in self.devices]

        # [self.get_fpga_configuration_register(dev) for dev in self.devices]

        if self.args.laser_enable:
            [self.set_laser_enable(dev, 1) for dev in self.devices]

        self.do_acquisitions()

        if self.args.laser_enable:
            [self.set_laser_enable(dev, 0) for dev in self.devices]

        if self.args.trigger_enable:
            [self.set_trigger_source(dev, 0) for dev in self.devices]

    def list(self):
        print("%-6s %-16s %-16s %3s %6s %-10s %-10s" % ("PID", "Model", "Serial", "Fmt", "Pixels", "FW", "FPGA"))
        for dev in self.devices:
            print("0x%04x %-16s %-16s %3d %6d %-10s %-10s" % (
                dev.idProduct, 
                dev.eeprom["model"], 
                dev.eeprom["serial_number"],
                dev.eeprom["format"],
                dev.eeprom["pixels"],
                dev.fw_version,
                dev.fpga_version))

    ############################################################################
    # opcodes
    ############################################################################

    def reset_fpga(self, dev):
        print("resetting FPGA on %s" % dev.eeprom["serial_number"])
        self.send_cmd(dev, 0xb5)

    # only supported on Gen 1.5
    def get_fpga_configuration_register(self, dev):
        raw = self.get_cmd(dev, 0xb3, lsb_len=2, label="GET_FPGA_CONFIGURATION_REGISTER")
        log.debug(f"FPGA Configuration Register: 0x{raw:04x} ({label})")
        return raw

    def get_firmware_version(self, dev):
        result = self.get_cmd(dev, 0xc0)
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self, dev):
        s = ""
        result = self.get_cmd(dev, 0xb4)
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
                    s += chr(c)
        return s

    def set_dfu(self, dev):
        print("setting DFU on %s" % dev.eeprom["serial_number"])
        self.send_cmd(dev, 0xfe)

    def set_laser_enable(self, dev, flag):
        self.debug("setting laserEnable to %s" % ("on" if flag else "off"))
        self.send_cmd(dev, 0xbe, 1 if flag else 0)

    def set_trigger_source(self, dev, n):
        self.debug(f"setting triggerSource to {n}")
        self.send_cmd(dev, 0xd2, n)

    def set_continuous_acquisition(self, dev, n):
        self.debug(f"setting continuous acquisition to {n}")
        self.send_cmd(dev, 0xc8, n)

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

    def do_acquisitions(self):
        outfile = open(self.args.outfile, 'w') if self.args.outfile is not None else None
        for i in range(self.args.spectra):
            for dev in self.devices:
                spectrum = self.get_spectrum(dev) if not self.args.trigger_enable else self.get_spectrum_trigger(dev)
                now = datetime.now()
                print("%s Spectrum %3d/%3d %s ..." % (now, i, self.args.spectra, spectrum[:10]))
                if outfile is not None:
                    outfile.write("%s, %s\n" % (now, ", ".join([str(x) for x in spectrum])))

                if self.args.laser_enable:
                    self.get_laser_temperature(dev)

            self.debug(f"sleeping {self.args.delay_ms}ms")
            sleep(self.args.delay_ms / 1000.0 )

        if outfile is not None:
            outfile.close()

    def get_spectrum(self, dev):
        timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2
        self.send_cmd(dev, 0xad, 1)
        bytes_to_read = dev.eeprom["pixels"] * 2

        self.debug(f"blocking on read of {bytes_to_read} bytes ({timeout_ms}ms timeout)")
        data = dev.read(0x82, bytes_to_read, timeout=timeout_ms)

        return self.demarshal_spectrum(data)

    def get_spectrum_trigger(self, dev):
        now = datetime.now()
        print(f"{now} waiting for trigger..", end='')  # note we don't send an AQUIRE
        while True:
            try:
                print(".", end='')
                data = dev.read(0x82, dev.eeprom["pixels"] * 2, timeout=1000)
                if data is not None:
                    now = datetime.now()
                    ms_since_last = (now - self.last_acquire).total_seconds() * 1000.0
                    self.last_acquire = now

                    print()
                    print(f"{now} received! ({ms_since_last:.2f}ms since last)")

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
