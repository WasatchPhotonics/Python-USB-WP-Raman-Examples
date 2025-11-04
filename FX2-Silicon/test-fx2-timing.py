#!/usr/bin/env python -u

import argparse
import usb.core
import time
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
        parser.add_argument("--count", type=int, default=10)
        parser.add_argument("--pixels", type=int, default=1024)
        parser.add_argument("--delay-ms", type=int, default=0)
        parser.add_argument("--int-time-ms", type=int, default=100)
        self.args = parser.parse_args()

        fw_rev = self.get_firmware_rev()
        fpga_rev = self.get_fpga_rev()
        print(f"connected to VID 0x{self.dev.idVendor:04x}, PID 0x{self.dev.idProduct:04x} with firmware {fw_rev} and FPGA {fpga_rev}")

    def i2c_write(self, address, buf):
        bRequest = 0x90
        wValue = address
        wIndex = len(buf)
        print(f"i2c_write: sending bRequest 0x{bRequest:02x}, wValue 0x{wValue:02x}, wIndex 0x{wIndex:02x}, buf {buf}")
        self.dev.ctrl_transfer(H2D, bRequest, address, len(buf), buf)

    def get_firmware_rev(self):
        data = self.dev.ctrl_transfer(D2H, 0xc0, 0, 0, 4, None)
        return ".".join(reversed([str(int(x)) for x in data]))

    def get_fpga_rev(self):
        data = self.dev.ctrl_transfer(D2H, 0xb4, 0, 0, 7, None)
        return "".join(chr(x) for x in data)

    def set_integration_time_ms(self, ms):
        print(f"setting integration time to {ms}")
        self.dev.ctrl_transfer(H2D, 0xb2, ms, 0, Z, TIMEOUT) # only implementing 16-bit here

    def set_laser_enable(self, flag):
        print(f"setting laser_enable {flag}")
        self.dev.ctrl_transfer(H2D, 0xbe, 1 if flag else 0, 0, Z, TIMEOUT) 

    def get_detector_temperature_raw(self):
        return self.get_code(0xd7, msb_len=2)

    def get_laser_temperature_raw(self):
        return self.get_code(0xd5, wLength=2, lsb_len=2) & 0xfff

    def get_laser_enabled(self):
        return 0 != self.get_code(0xe2, msb_len=1)

    def get_spectrum(self):
        self.dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)
        if self.args.pixels == 1024:
            data = self.dev.read(0x82, self.args.pixels * 2, TIMEOUT)
        elif self.args.pixels == 2048:
            data = self.dev.read(0x82, self.args.pixels, TIMEOUT)
            data.extend(self.dev.read(0x86, self.args.pixels, TIMEOUT))
        else:
            raise Exception("invalid pixels {self.args.pixels}")

        return [i + (j << 8) for i, j in zip(data[::2], data[1::2])]

    def get_code(self, bRequest, wValue=0, wIndex=0, wLength=64, msb_len=None, lsb_len=None):
        result = self.dev.ctrl_transfer(0xc0, bRequest, wValue, wIndex, wLength, TIMEOUT)
        value = 0
        if msb_len is not None:
            for i in range(msb_len):
                value = value << 8 | result[i]
            return value
        elif lsb_len is not None:
            for i in range(lsb_len):
                if i < len(result):
                    value = (result[i] << (8 * i)) | value
            return value
        else:
            return result

    def do_test(self):
        for i in range(self.args.count):
            start = datetime.now()
            spectrum = self.get_spectrum()
            spec_ms = (datetime.now() - start).total_seconds() * 1000

            start = datetime.now()
            enabled = 1 if self.get_laser_enabled() else 0
            en_ms = (datetime.now() - start).total_seconds() * 1000

            start = datetime.now()
            det_temp = self.get_detector_temperature_raw()
            det_temp_ms = (datetime.now() - start).total_seconds() * 1000

            start = datetime.now()
            las_temp = self.get_laser_temperature_raw()
            las_temp_ms = (datetime.now() - start).total_seconds() * 1000

            print(f"{datetime.now()} loop {i+1:2d}: spec_s {spec_ms:5.2f}ms, enabled {enabled} ({en_ms:6.2f}ms elapsed), det_temp 0x{det_temp:04x} ({det_temp_ms:6.2f}ms elapsed), las_temp 0x{las_temp:04x} ({las_temp_ms:6.2f}ms elapsed), {len(spectrum)} pixels: {spectrum[:5]}")

            time.sleep(self.args.delay_ms / 1000.0)

    def run(self):
        print(f"setting integration time {self.args.int_time_ms}ms")
        self.set_integration_time_ms(self.args.int_time_ms)

        print("BEFORE firing laser")
        self.do_test()

        print("FIRING LASER")
        self.set_laser_enable(True)

        print("WHILE firing laser")
        self.do_test()

        print("DISABLING LASER")
        self.set_laser_enable(False)

        print("AFTER disabling laser")
        self.do_test()

fixture = Fixture()
fixture.run()
