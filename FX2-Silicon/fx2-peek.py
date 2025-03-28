#!/usr/bin/env python

import usb.core
import argparse
import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 3000

class Fixture():
    def __init__(self):
        if len(sys.argv) != 3:
            print(f"Usage: python {sys.argv[0]} <addr> <len>   (addr in hex, len in dec)")
            sys.exit(1)

        progname = sys.argv.pop(0)
        self.address = int(sys.argv.pop(0), 16)
        self.length = 1 # int(sys.argv.pop(0))

        # find the FIRST connected spectrometer of the given PID
        self.pid = 0x1000
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print(f"No spectrometers found with PID 0x{self.pid:04x}")
            sys.exit(1)

    def run(self):
        data = self.get_cmd(0xe9, value = self.address, index = self.length, length = self.length)
        if self.address == 0x12:
           ctrl_reg_val = data[1]
           ctrl_reg_val <<= 8
           ctrl_reg_val |= data[0]
           print("Ctrl Reg Val 0x{:04x}".format(ctrl_reg_val))
        data_hex = " ".join( [ f"{v:02x}" for v in data ] )
        print(f"0x{self.address:02x} << 0x{data_hex} ({len(data)} bytes)")
        
    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            if self.is_arm():
                buf = [0] * 8
            else:
                buf = ""
        # print("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None):
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        print(result)
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
