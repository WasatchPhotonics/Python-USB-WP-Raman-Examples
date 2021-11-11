#!/usr/bin/env python -u

import os
import sys
import usb.core
import argparse

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

def process_cmd_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",               type=int,            help="how many LINES of spectra to read (default 20)", default=20)
    parser.add_argument("--debug",               action="store_true", help="verbose output")
    parser.add_argument("--fast",                action="store_true", help="fast mode")
    parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms) (default 10)", default=10)
    parser.add_argument("--pid",                 default="4000",      help="USB PID in hex (default 4000)", choices=["1000", "2000", "4000"])
    parser.add_argument("--pixels",              type=int,            help="expected pixels (default 1952)", default=1952)
    parser.add_argument("--start-line",          type=int,            help="vertical binning start line")
    parser.add_argument("--stop-line",           type=int,            help="vertical binning stop line")
    return parser.parse_args()

def send_code(cmd, value=0, index=0, buf=Z, timeout=TIMEOUT_MS):
    if args.debug:
        print("DEBUG: sending HOST_TO_DEVICE cmd 0x%02x, value 0x%04x, index 0x%04x, buf %s, timeout %d\n" % (
            cmd, value, index, buf, timeout))
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, timeout)

args = process_cmd_args()

# connect
dev = usb.core.find(idVendor=0x24aa, idProduct=int(args.pid, 16))
if dev is None:
    print("No spectrometers found")
    sys.exit(0)

if os.name == "posix":
    dev.set_configuration(1)
    usb.util.claim_interface(dev, 0)

# report firmware revisions
fw = ".".join(reversed([str(x) for x in dev.ctrl_transfer(DEVICE_TO_HOST, 0xc0, 0, 0, 64)]))
fpga = "".join([chr(x) for x in dev.ctrl_transfer(DEVICE_TO_HOST, 0xb4, 0, 0, 64)])
print("FW %s FPGA %s" % (fw, fpga))

print("setting integration time %dms" % args.integration_time_ms)
send_code(0xb2, args.integration_time_ms & 0xffff)

if args.start_line is not None:
    print("setting start_line %d" % args.start_line)
    send_code(0xff, 0xf4, args.start_line)

if args.stop_line is not None:
    print("setting stop_line %d" % args.stop_line)
    send_code(0xff, 0xf5, args.stop_line)

print("Enabling area scan")
send_code(0xeb, 1)

if args.fast:
    send_code(0xad)

print("Looping over %d spectra (lines)" % args.count)
for linenum in range(args.count):

    if not args.fast:
        send_code(0xad)

    # read spectrum
    data = dev.read(0x82, args.pixels * 2)

    spectrum = []
    for i in range(0, len(data), 2):
        spectrum.append(data[i] | (data[i+1] << 8))

    print("Spectrum %3d/%3d: %s ..." % (linenum + 1, args.count, spectrum[:10]))
