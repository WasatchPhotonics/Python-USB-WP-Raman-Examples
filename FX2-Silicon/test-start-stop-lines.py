#!/usr/bin/env python -u

import argparse
import usb.core
import sys
from datetime import datetime

H2D=0x40
D2H=0xC0
Z = [0] * 8
TIMEOUT = 5000

class Fixture:

    def __init__(self):
        dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
        if dev is None:
            print("No spectrometer found")
            sys.exit()
        self.dev = dev

        parser = argparse.ArgumentParser()
        parser.add_argument("--pixels", type=int, default=1024)
        parser.add_argument("--start-line", type=int)
        parser.add_argument("--stop-line", type=int)
        self.args = parser.parse_args()

        if self.args.start_line is not None:
            self.set_start_line(self.args.start_line)
        if self.args.stop_line is not None:
            self.set_stop_line(self.args.stop_line)

    def i2c_write(self, address, buf):
        bRequest = 0x90
        wValue = address
        wIndex = len(buf)
        print(f"i2c_write: sending bRequest 0x{bRequest:02x}, wValue 0x{wValue:02x}, wIndex 0x{wIndex:02x}, buf {buf}")
        self.dev.ctrl_transfer(H2D, bRequest, address, len(buf), buf)

    def set_start_line(self, start):
        print(f"setting start line to {start}")
        self.i2c_write(0x29, [start])

    def set_stop_line(self, stop):
        print(f"setting stop line to {stop}")
        self.i2c_write(0x2A, [stop])

    def set_integration_time_ms(self, ms):
        print(f"setting integration time to {ms}")
        self.dev.ctrl_transfer(H2D, 0xb2, ms, 0, Z, TIMEOUT) # only implementing 16-bit here

    def get_spectrum(self):
        self.dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)
        if self.args.pixels == 1024:
            data = self.dev.read(0x82, self.args.pixels * 2)
        elif self.args.pixels == 2048:
            data = self.dev.read(0x82, self.args.pixels )
            data.extend(self.dev.read(0x86, self.args.pixels))
        else:
            raise Exception("invalid pixels {self.args.pixels}")

        return [i + (j << 8) for i, j in zip(data[::2], data[1::2])]

    def run(self):
        for ms in [10, 100, 1000]:
            self.set_integration_time_ms(ms)
            for i in range(5):
                spectrum = self.get_spectrum()
                print(f"{datetime.now()}: read spectrum of {len(spectrum)} pixels: sum {sum(spectrum):0.1e}, data {spectrum[0:10]}")

fixture = Fixture()
fixture.run()
