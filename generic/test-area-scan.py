#!/usr/bin/env python -u

import sys
import usb.core
import argparse

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

# process cmd-line args
parser = argparse.ArgumentParser()
parser.add_argument("--count",               type=int,       help="how many spectra to read (default 20)", default=20)
parser.add_argument("--integration-time-ms", type=int,       help="integration time (ms) (default 10)", default=10)
parser.add_argument("--pid",                 default="4000", help="USB PID in hex (default 4000)", choices=["1000", "2000", "4000"])
parser.add_argument("--pixels",              type=int,       help="expected pixels (default 1952)", default=1952)
parser.add_argument("--start-line",          type=int,       help="vertical binning start line")
parser.add_argument("--stop-line",           type=int,       help="vertical binning stop line")
args = parser.parse_args()

# connect
dev = usb.core.find(idVendor=0x24aa, idProduct=int(args.pid, 16))

# report firmware revisions
fw = ".".join(reversed([str(x) for x in dev.ctrl_transfer(DEVICE_TO_HOST, 0xc0, 0, 0, 64)]))
fpga = "".join([chr(x) for x in dev.ctrl_transfer(DEVICE_TO_HOST, 0xb4, 0, 0, 64)])
print("FW %s FPGA %s" % (fw, fpga))

print("setting integration time %dms" % args.integration_time_ms)
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, args.integration_time_ms & 0xffff, 0, Z, TIMEOUT_MS)

if args.start_line is not None:
    print("setting start_line %d" % args.start_line)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0xf4, args.start_line, Z, TIMEOUT_MS)

if args.stop_line is not None:
    print("setting stop_line %d" % args.stop_line)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0xf5, args.stop_line, Z, TIMEOUT_MS)

print("Enabling area scan")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xeb, 1, 0, Z, TIMEOUT_MS)

print("Looping over %d spectra" % args.count)
for linenum in range(args.count):
    # send SW trigger
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, Z, TIMEOUT_MS)

    # read spectrum
    data = dev.read(0x82, args.pixels * 2)

    spectrum = []
    for i in range(0, len(data), 2):
        spectrum.append(data[i] | (data[i+1] << 8))

    print("Spectrum %3d/%3d: %s ..." % (linenum + 1, args.count, spectrum[:10]))
