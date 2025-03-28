#!/usr/bin/env python

import usb.core
import argparse
import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

class Fixture():
    def __init__(self):
        if len(sys.argv) < 2:
            print(f"Usage: python {sys.argv[0]} <line_cnt in decimal>")
            sys.exit(1)

        progname = sys.argv.pop(0)
        self.line_cnt = int(sys.argv.pop(0), 10)

        # find the FIRST connected spectrometer of the given PID
        self.pid = 0x1000
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=self.pid)
        if not self.dev:
            print(f"No spectrometers found with PID 0x{self.pid:04x}")
            sys.exit(1)

    def run(self):
        # initialize buffer from values
        buf = [ x for x in self.values ]

        # ensure at least 8 elements in buffer
        while len(buf) < 8:
            buf.append(0)

        self.send_cmd(0x90, self.address, len(self.values), buf=buf)

        values_hex = "0x" + " ".join([ f"{v:02x}" for v in self.values ])
        print(f"0x{self.address:02x} >> {values_hex}")
        
    def send_cmd(self, cmd, value=0, index=0, buf=None):
        print("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None):
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)

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
    if fixture.line_cnt < 1 or fixture.line_cnt > 70:
       print("line cnt range is 1 to 70 !!")
    else:
       print("line_cnt is ", fixture.line_cnt)
       fixture.send_cmd(0xa6, fixture.line_cnt)
    # fixture.run()
