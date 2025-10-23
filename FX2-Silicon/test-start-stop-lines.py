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
        parser.add_argument("--start-line", type=int, default=0)
        parser.add_argument("--stop-line", type=int, default=63)
        parser.add_argument("--pixels", type=int, default=1024)
        parser.add_argument("--debug", action="store_true")
        parser.add_argument("--count", type=int, default=5)
        parser.add_argument("--loop", type=int, default=1)
        self.args = parser.parse_args()

        fpga_rev = self.get_fpga_rev()
        fw_rev = self.get_firmware_rev()

        print(f"connected to VID 0x{self.dev.idVendor:04x}, PID 0x{self.dev.idProduct:04x} with firmware {fw_rev} and FPGA {fpga_rev}")

    def run(self):
        self.set_start_line(self.args.start_line)
        self.set_stop_line(self.args.stop_line)

        for j in range(self.args.loop):
            for ms in [10, 100, 1000]:
                self.set_integration_time_ms(ms)
                for i in range(self.args.count):
                    spectrum = self.get_spectrum()
                    print(f"{datetime.now()}: read spectrum {i}-of-{self.args.count} (loop {j}-of-{self.args.loop}): sum {sum(spectrum):0.1e}, data {spectrum[0:5]}")

    def get_firmware_rev(self):
        data = self.dev.ctrl_transfer(D2H, 0xc0, 0, 0, 4, None)
        return ".".join(reversed([str(int(x)) for x in data]))

    def get_fpga_rev(self):
        data = self.dev.ctrl_transfer(D2H, 0xb4, 0, 0, 7, None)
        return "".join(chr(x) for x in data)

    def set_start_line(self, start):
        print(f"setting start line to {start}")
        self.i2c_write(0x29, [ start ])

    def set_stop_line(self, stop):
        print(f"setting stop line to {stop}")
        self.i2c_write(0x2A, [ stop ])

    def set_integration_time_ms(self, ms):
        print(f"setting integration time to {ms}")
        self.dev.ctrl_transfer(H2D, 0xb2, ms, 0, 0, TIMEOUT) # only implementing 16-bit here

    def get_spectrum(self):
        self.send_cmd(0xad, data_or_wLength=Z, label="ACQUIRE")
        if self.args.pixels == 1024:
            data = self.dev.read(0x82, self.args.pixels * 2, TIMEOUT)
        elif self.args.pixels == 2048:
            data = self.dev.read(0x82, self.args.pixels, TIMEOUT)
            data.extend(self.dev.read(0x86, self.args.pixels, TIMEOUT))
        else:
            raise Exception("invalid pixels {self.args.pixels}")

        return [i + (j << 8) for i, j in zip(data[::2], data[1::2])]

    # def i2c_write(self, addr, buf):
        #self.send_cmd(0x90, addr, len(buf), data_or_wLength=buf, label="I2C_POKE")
        # self.send_cmd(0x90, addr, len(buf), data_or_wLength=buf, label="I2C_POKE", timeout=None)

    def i2c_write(self, address, buf):
        bRequest = 0x90
        wValue = address
        wIndex = len(buf)
        print(f"i2c_write: sending bRequest 0x{bRequest:02x}, wValue 0x{wValue:02x}, wIndex 0x{wIndex:02x}, buf {buf}")
        self.dev.ctrl_transfer(H2D, bRequest, address, len(buf), buf)

    def send_cmd(self, bRequest, wValue=0, wIndex=0, data_or_wLength=0, timeout=TIMEOUT, label=None):
        result = self.dev.ctrl_transfer(H2D, bRequest, wValue, wIndex, data_or_wLength, timeout) 
        if self.args.debug:
            print(f"{datetime.now()}: sending bRequest 0x{bRequest:02x}, wValue 0x{wValue:04x}, wIndex 0x{wIndex:04x}, data_or_wLength {data_or_wLength} returned {result} ({label})")

fixture = Fixture()
fixture.run()
