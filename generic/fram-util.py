#!/usr/bin/env python

import sys
import usb.core
import argparse

from time import sleep

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000
PAGES_PER_SPECTRA = 62 # 1952 pixels x 2 bytes/pixel = 3904 bytes / 64 bytes/page = 61 pages + 1 "metadata" = 62

PAGE_SIZE = 64 # number of bytes transferred in an FRAM "page"

class Fixture(object):
    def __init__(self):
        self.fram_data = None
        self.subformat = None

        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",          action="store_true",    help="debug output")
        parser.add_argument("--pid",            default="4000",         help="USB PID in hex (default 4000)", choices=["1000", "2000", "4000"])
        parser.add_argument("--fram-pages",     type=int,               help="number of 64-byte pages to read from FRAM (default 61)", default=61)
        parser.add_argument("--erase",          action="store_true",    help="erase all")
        parser.add_argument("--spectrum-index", type=int,               help="spectrum index", default=0)
        self.args = parser.parse_args()

        self.pid = int(self.args.pid, 16)

        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print("No spectrometers found with PID 0x%04x" % self.pid)

    def run(self):
        if self.args.erase:
            self.erase_fram()
        else:            
            self.read_fram()
            self.dump_fram()
            
    def read_fram(self):
        print("Reading FRAM...")
        self.fram_data = []
        for i in range(self.args.fram_pages):
            index = self.args.spectrum_index + i
            buf = self.get_cmd(cmd=0xff, value=0x25, index=index , length=PAGE_SIZE)
            self.fram_data.extend(buf)
            print("  read page %3d (%2d / %2d)" % (index, i, self.args.fram_pages))
            sleep(0.1)
        print()

    def dump_fram(self):
        spectrum = []
        pixel = 0 # index of pixel, e.g. (0, 1951)
        for i in range(0, len(self.fram_data), 2):
            lsb = self.fram_data[i]
            msb = self.fram_data[i+1]
            intensity = (msb << 8) | lsb

            pixel = pixel + 1
            spectrum.append(intensity)

            print("Pixel %4d: 0x%02x 0x%02x  %5d" % (pixel, lsb, msb, intensity))

    def erase_fram(self):
        print("FRAM erased")
        self.send_cmd(cmd=0xff, value=0x26)

    ############################################################################
    # Utility Methods
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value, index=0, buf=None):
        if buf is None:
            if self.pid == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(%02x, %02x, %04x, %04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64):
        return self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

fixture = Fixture()
if fixture.dev:
    fixture.run()
