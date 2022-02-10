#!/usr/bin/env python

# * read dark with a certain int time
# * turn laser on at a certain power level, does not need to be calibrated
# * read signal with the same int time
# * turn laser off
#
# The script then repeats this over and over.

import sys
import re
from time import sleep
from datetime import datetime

import matplotlib.pyplot as plt
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
        self.outfile = None
        self.dark = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--count",               type=int,            help="read the given number of spectra (default 1)", default=1)
        parser.add_argument("--dark",                action="store_true", help="collect dark and perform dark correction (default off)")
        parser.add_argument("--debug",               action="store_true", help="debug output (default off)")
        parser.add_argument("--delay-ms",            type=int,            help="delay n ms between spectra (default 10)", default=10)
        parser.add_argument("--gain-db",             type=float,          help="gain in dB (default 8.0)", default=8.0)
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms) (default 100)", default=100)
        parser.add_argument("--laser-power",         type=int,            help="laser power as a percentage (range 1-100) (default 100)", default=100)
        parser.add_argument("--laser-warmup-ms",     type=int,            help="laser warmup delay in ms (default 4000)", default=4000)
        parser.add_argument("--outfile",             type=str,            help="outfile to save full spectra")
        parser.add_argument("--plot",                action="store_true", help="graph spectra after collection (default off)")
        parser.add_argument("--scans-to-average",    type=int,            help="scans to average (default 0)", default=1)
        self.args = parser.parse_args()

        self.devices = usb.core.find(find_all=True, idVendor=0x24aa, idProduct=0x4000)
        if len(self.devices) == 0:
            print("No spectrometers found")
        self.device = self.devices[0]

        # claim device
        self.debug("claiming spectrometer")
        self.device.set_configuration(1)
        usb.util.claim_interface(self.device, 0)
        self.debug("claimed device")

        # read configuration
        self.fw_version = self.get_firmware_version()
        self.fpga_version = self.get_fpga_version()
        self.read_eeprom()
        self.generate_wavelengths()
        print(f"Connected to {self.eeprom['model']} {self.eeprom['serial_number']} with {self.eeprom['pixels']} ({self.wavelengths[0]}, {self.wavelengths[-1]}nm) ({self.wavenumbers[0]}, {self.wavenumbers[-1]}cm-1)")

    def read_eeprom(self):
        self.buffers = [self.get_cmd(self.device, 0xff, 0x01, page) for page in range(8)]

        # parse key fields (extend as needed)
        self.eeprom = {}
        self.eeprom["format"]        = self.unpack((0, 63,  1), "B")
        self.eeprom["model"]         = self.unpack((0,  0, 16), "s")
        self.eeprom["serial_number"] = self.unpack((0, 16, 16), "s")
        self.eeprom["pixels"]        = self.unpack((2, 16,  2), "H")
        self.eeprom["excitation_nm"] = self.unpack((3, 36,  4), "f")
        self.eeprom["wavecal_C0"]    = self.unpack((1,  0,  4), "f")
        self.eeprom["wavecal_C1"]    = self.unpack((1,  4,  4), "f")
        self.eeprom["wavecal_C2"]    = self.unpack((1,  8,  4), "f")
        self.eeprom["wavecal_C3"]    = self.unpack((1, 12,  4), "f")

    def generate_wavelengths(self):
        self.wavelengths = []
        self.wavenumbers = []
        for i in range(self.eeprom["pixels"]):
            wavelength = self.eeprom["wavecal_C0"] \
                       + self.eeprom["wavecal_C1"] * i \
                       + self.eeprom["wavecal_C2"] * i * i \
                       + self.eeprom["wavecal_C3"] * i * i * i
            wavenumber = 1e7 / self.eeprom["excitation_nm"] - 1e7 / wavelength
            self.wavelengths.append(wavelength)
            self.wavenumbers.append(wavenumber)

    ############################################################################
    # Commands
    ############################################################################

    def run(self):

        # disable laser
        self.set_laser_enable(False)

        # set integration time
        self.set_integration_time_ms(self.args.integration_time_ms)

        # set gain dB
        self.set_gain_db(self.args.gain_db)

        # take dark
        if self.args.dark:
            self.dark = self.get_averaged_spectrum()

        # open outfile
        if self.args.outfile is not None:
            self.outfile = open(self.args.outfile, 'w')

            # header rows
            self.outfile.write("pixel, %s\n" % (", ".join([x for x in range(self.eeprom["pixels"]))))
            self.outfile.write("wavelength, %s\n" % (", ".join(["{x:f2}" for x in self.wavelengths])))
            self.outfile.write("wavenumber, %s\n" % (", ".join(["{x:f2}" for x in self.wavenumbers])))

        # enable laser
        self.set_laser_enable(True)

        # take measurements
        spectra = []
        try:
            for i in range(self.args.count):
                # take measurement
                spectrum = self.get_averaged_spectrum()
                if self.dark is not None:
                    spectrum -= dark
                spectra.append(spectrum)
                
                # save measurement
                now = datetime.now()
                print("%s Spectrum %3d/%3d %s ..." % (now, i, self.args.count, spectrum[:10]))
                if outfile is not None:
                    self.outfile.write("%s, %s\n" % (now, ", ".join(["{x:f2}" for x in spectrum])))

                # delay before next
                sleep(self.args.delay_ms / 1000.0 )
        except:
            print("caught exception reading spectra")

        # disable laser
        self.set_laser_enable(False)

        # close file
        if self.outfile is not None:
            self.outfile.close()

        # graph
        if self.args.plot:
            for a in spectra:
                plt.plot(a)
            plt.title(f"integration time {args.integration_time_ms}ms, gain {args.gain_db}dB, count {args.count}")
            plt.show()

    ############################################################################
    # opcodes
    ############################################################################

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

    def set_laser_enable(self, flag):
        self.debug(f"setting laserEnable {flag}")
        self.send_cmd(0xbe, 1 if flag else 0)

        if flag and self.args.laser_warmup_ms > 0:
            self.debug("starting aser warmup")
            sleep(self.args.laser_warmup_ms / 1000.0)
            self.debug("finished aser warmup")

    def set_integration_time_ms(self, ms):
        if ms < 1 or ms > 0xffff:
            print("ERROR: integrationTimeMS requires positive uint16")
            return

        self.debug(f"setting integrationTimeMS to {ms}")
        self.send_cmd(0xb2, ms)

    def set_gain_db(self, db):
        raw = db << 8 
        self.debug("setting gainDB 0x%04x (FunkyFloat)" % gainDB)
        self.send_cmd(0xb7, raw)

    def set_modulation_enable(self, flag):
        self.debug(f"setting laserModulationEnable {flag}")
        self.send_cmd(0xbd, 1 if flag else 0)

    def set_raman_mode(self, flag):
        self.debug(f"setting ramanMode {flag}")
        self.send_cmd(0xff, 0x16, 1 if flag else 0)

    def set_raman_delay_ms(self, ms):
        if ms < 0 or ms > 0xffff:
            print("ERROR: ramanDelay requires uint16")
            return

        self.debug(f"setting ramanDelay {ms} ms")
        self.send_cmd(0xff, 0x20, ms)

    def set_watchdog_sec(self, sec):
        if sec < 0 or sec > 0xffff:
            print("ERROR: laserWatchdog requires uint16")
            return

        self.debug(f"setting laserWatchdog {sec} sec")
        self.send_cmd(0xff, 0x18, sec)

    def get_averaged_spectrum(self):
        spectrum = self.get_spectrum()
        if spectrum is None or self.args.scans_to_average < 2:
            return spectrum

        for i in range(self.args.scans_to_average - 1):
            tmp = self.get_spectrum()
            if tmp is None:
                return
            for j in range(len(spectrum)):
                spectrum[j] += tmp[i]

        for i in range(len(spectrum)):
            spectrum[i] = spectrum[i] / self.args.scans_to_average
        return spectrum

    def get_spectrum(self):
        timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2
        self.send_cmd(self.device, 0xad, 1)
        data = self.device.read(0x82, dev.eeprom["pixels"] * 2, timeout=timeout_ms)
        if data is None:
            return

        spectrum = []
        for i in range(0, len(data), 2):
            spectrum.append(data[i] | (data[i+1] << 8))

        if len(spectrum) != self.eeprom["pixels"]:
            return

        return spectrum

    ############################################################################
    # Utility Methods
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print(f"DEBUG: {msg}")

    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            buf = [0] * 8
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
