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

# An extensible, stateful "Test Fixture" 
class Fixture(object):

    ############################################################################
    # Lifecycle 
    ############################################################################

    def __init__(self):
        self.outfile = None
        self.device = None
        self.dark = None

        # parse cmd-line args
        parser = argparse.ArgumentParser()
        parser.add_argument("--bin2x2",              action="store_true", help="apply 2x2 binning")
        parser.add_argument("--count",               type=int,            help="read the given number of spectra (default 1)", default=1)
        parser.add_argument("--dark",                action="store_true", help="collect dark and perform dark correction")
        parser.add_argument("--debug",               action="store_true", help="debug output (default off)")
        parser.add_argument("--delay-ms",            type=int,            help="delay n ms between spectra (default 10)", default=10)
        parser.add_argument("--fire-laser",          action="store_true", help="to avoid accidents, WILL NOT fire laser unless specified")
        parser.add_argument("--gain-db",             type=float,          help="gain in dB (default 8.0)", default=8.0)
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms) (default 100)", default=100)
        parser.add_argument("--laser-power",         type=int,            help="laser power as a percentage (range 1-100) (default 100)", default=100)
        parser.add_argument("--laser-warmup-ms",     type=int,            help="laser warmup delay in ms (default 4000)", default=4000)
        parser.add_argument("--outfile",             type=str,            help="outfile to save full spectra")
        parser.add_argument("--plot",                action="store_true", help="graph spectra after collection")
        parser.add_argument("--scans-to-average",    type=int,            help="scans to average (default 0)", default=1)
        self.args = parser.parse_args()

        # grab first spectrometer on the chain
        device = usb.core.find(idVendor=0x24aa, idProduct=0x4000)
        if device is None:
            print("No spectrometers found")
            return
        self.debug(device)
        self.device = device

        # claim device (I'm never sure when this is required)
        if False:
            self.debug("claiming spectrometer")
            self.device.set_configuration(1)
            usb.util.claim_interface(self.device, 0)
            self.debug("claimed device")

        # read configuration
        self.fw_version = self.get_firmware_version()
        self.fpga_version = self.get_fpga_version()
        self.read_eeprom()
        self.generate_wavelengths()
        print(f"Connected to {self.model} {self.serial_number} with {self.pixels} pixels ({self.wavelengths[0]:.2f}, {self.wavelengths[-1]:.2f}nm) ({self.wavenumbers[0]:.2f}, {self.wavenumbers[-1]:.2f}cm-1)")
        print(f"ARM {self.fw_version}, FPGA {self.fpga_version}")

    def read_eeprom(self):
        self.buffers = [self.get_cmd(0xff, 0x01, page) for page in range(8)]

        # parse key fields (extend as needed)
        self.format         = self.unpack((0, 63,  1), "B")
        self.model          = self.unpack((0,  0, 16), "s")
        self.serial_number  = self.unpack((0, 16, 16), "s")
        self.pixels         = self.unpack((2, 16,  2), "H")
        self.excitation_nm  = self.unpack((3, 36,  4), "f")
        self.wavecal_C0     = self.unpack((1,  0,  4), "f")
        self.wavecal_C1     = self.unpack((1,  4,  4), "f")
        self.wavecal_C2     = self.unpack((1,  8,  4), "f")
        self.wavecal_C3     = self.unpack((1, 12,  4), "f")

    def generate_wavelengths(self):
        self.wavelengths = []
        self.wavenumbers = []
        for i in range(self.pixels):
            wavelength = self.wavecal_C0 \
                       + self.wavecal_C1 * i \
                       + self.wavecal_C2 * i * i \
                       + self.wavecal_C3 * i * i * i
            wavenumber = 1e7 / self.excitation_nm - 1e7 / wavelength
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

        # perform one throwaway (seems to help SiG)
        self.get_spectrum()

        # take dark
        if self.args.dark:
            print("taking dark")
            self.dark = self.get_averaged_spectrum()

        # open outfile
        if self.args.outfile is not None:
            self.outfile = open(self.args.outfile, 'w')

            # header rows
            self.outfile.write("pixel, %s\n"      % (", ".join([str(x) for x in range(self.pixels)])))
            self.outfile.write("wavelength, %s\n" % (", ".join([f"{x:.2f}" for x in self.wavelengths])))
            self.outfile.write("wavenumber, %s\n" % (", ".join([f"{x:.2f}" for x in self.wavenumbers])))

        # enable laser
        if self.args.fire_laser:
            self.set_laser_enable(True)
        else:
            print("*** not firing laser because --fire-laser not specified ***")

        # take measurements
        spectra = []
        try:
            for i in range(self.args.count):
                # take dark-corrected measurement
                spectrum = self.get_averaged_spectrum()
                if self.dark is not None:
                    spectrum -= dark
                spectra.append(spectrum)
                
                # save measurement
                now = datetime.now()
                print("%s Spectrum %3d/%3d %s ..." % (now, i+1, self.args.count, spectrum[:10]))
                if self.outfile is not None:
                    self.outfile.write("%s, %s\n" % (now, ", ".join([f"{x:.2f}" for x in spectrum])))

                # delay before next
                sleep(self.args.delay_ms / 1000.0 )
        except:
            print("caught exception reading spectra")
            traceback.print_exc()

        # disable laser
        self.set_laser_enable(False)

        # close file
        if self.outfile is not None:
            self.outfile.close()

        # graph
        if self.args.plot:
            for a in spectra:
                plt.plot(a)
            plt.title(f"integration time {self.args.integration_time_ms}ms, gain {self.args.gain_db}dB, count {self.args.count}")
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
        print(f"setting laserEnable {flag}")
        self.send_cmd(0xbe, 1 if flag else 0)

        if flag and self.args.laser_warmup_ms > 0:
            print(f"{datetime.now()} starting laser warmup")
            sleep(self.args.laser_warmup_ms / 1000.0)
            print(f"{datetime.now()} finished laser warmup")

    def set_integration_time_ms(self, ms):
        if ms < 1 or ms > 0xffff:
            print("ERROR: integrationTimeMS requires positive uint16")
            return

        self.debug(f"setting integrationTimeMS to {ms}")
        self.send_cmd(0xb2, ms)

    def set_gain_db(self, db):
        db = round(db, 1)
        msb = int(db)
        lsb = int((db - int(db)) * 10)
        raw = (msb << 8) | lsb
        self.debug("setting gainDB 0x%04x (FunkyFloat)" % raw)
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
        self.send_cmd(0xad, 0)
        data = self.device.read(0x82, self.pixels * 2, timeout=timeout_ms)
        if data is None:
            return

        spectrum = []
        for i in range(0, len(data), 2):
            spectrum.append(data[i] | (data[i+1] << 8))

        if len(spectrum) != self.pixels:
            return

        # stomp blank SiG pixels (first 3 and last)
        for i in range(3):
            spectrum[i] = spectrum[3]
        spectrum[-1] = spectrum[-2]

        # 2x2 binning
        if self.args.bin2x2:
            for i in range(self.pixels-1):
                spectrum[i] = (spectrum[i] + spectrum[i+1]) / 2.0

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
if fixture.device is not None:
    fixture.run()
