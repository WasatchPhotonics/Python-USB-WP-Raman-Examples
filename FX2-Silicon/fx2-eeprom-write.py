#!/usr/bin/env python

import usb.core
import argparse
import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

class Fixture():
    def __init__(self):
        if len(sys.argv) < 3:
            print(f"Usage: python {sys.argv[0]} <addr> <byte1> <byte2> ... <byte n> (all in hex)")
            sys.exit(1)

        progname = sys.argv.pop(0)
        self.address = int(sys.argv.pop(0), 16)
        self.values = [ int(x, 16) for x in sys.argv ] # copy remaining arguments into list of bytes

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

        self.send_cmd(0xa2, self.address, len(self.values), buf=buf)

        values_hex = "0x" + " ".join([ f"{v:02x}" for v in self.values ])
        print(f"0x{self.address:02x} >> {values_hex}")
        
    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            if self.is_arm():
                buf = [0] * 8
            else:
                buf = ""
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
    fixture.run()
