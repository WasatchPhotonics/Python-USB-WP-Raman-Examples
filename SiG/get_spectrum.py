#!/usr/bin/env python

import os
import sys
import usb.core
import argparse
import platform
import matplotlib.pyplot as plt

from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000

################################################################################
# parse command-line arguments
################################################################################

parser = argparse.ArgumentParser()
parser.add_argument("--integration-time-ms", type=int, default=400, help="default 400")
parser.add_argument("--gain-db",             type=int, default=8, help="default 8")
parser.add_argument("--delay-ms",            type=int, default=10, help="how long to delay between spectra (default 10)")
parser.add_argument("--count",               type=int, default=1, help="how many spectra to take")
parser.add_argument("--throwaways",          type=int, default=2, help="how many throwaways to take (default 2)")
parser.add_argument("--pixels",              type=int, default=1920, help="default 1920")
parser.add_argument("--plot",                action="store_true", help="display graph")
parser.add_argument("--debug",               action="store_true", help="debug output")
parser.add_argument("--outfile",             type=str, help="save spectra")
args = parser.parse_args()

################################################################################
# connect
################################################################################

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

if args.debug:
    print(dev)

if os.name == "posix":
    if not "macOS" in platform.platform():
        dev.set_configuration()
    usb.util.claim_interface(dev, 0)

################################################################################
# configure
################################################################################

if False:
    print("sending SET_INTEGRATION_TIME_MS -> %d ms" % args.integration_time_ms)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, args.integration_time_ms, 0, BUF, TIMEOUT_MS)

    gainDB = args.gain_db << 8 
    print("sending GAIN_DB -> 0x%04x (FunkyFloat)" % gainDB)
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gainDB, 0, BUF, TIMEOUT_MS) 

################################################################################
# collect
################################################################################

spectra = []
for i in range(args.count + args.throwaways):
    if i != 0:
        print(f"sleeping {args.delay_ms}ms")
        sleep(args.delay_ms / 1000.0)

    print("sending ACQUIRE")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

    print(f"reading {args.pixels} from bulk endpoint")
    data = dev.read(0x82, args.pixels * 2) 

    print(f"read {len(data)} bytes")
    if len(data) != args.pixels * 2:
        print("ERROR: read %d bytes" % len(data))
        sys.exit(1)

    if i < args.throwaways:
        print("dumping throwaway")
    else:
        print("storing")
        spectrum = []
        for px in range(args.pixels):
            spectrum.append(data[px*2] | (data[px*2 + 1] << 8)) # demarshal LSB-MSB to uint16
        spectra.append(spectrum)

################################################################################
# process 
################################################################################

print("max = %d" % max(max(spectra)))
print("min = %d" % min(min(spectra)))
print("sum = %e" % sum([sum(spectrum) for spectrum in spectra]))

if args.outfile:
    print(f"writing {args.outfile}")
    with open(args.outfile, 'w') as f:
        for i in range(args.pixels):
            f.write("%s\n" % ', '.join([str(a[i]) for a in spectra]))
            
if args.plot:
    [plt.plot(a) for a in spectra]
    plt.title(f"integration time {args.integration_time_ms}ms, gain {args.gain_db}dB, count {args.count}, throwaways {args.throwaways}, delay {args.delay_ms}ms")
    plt.show()
