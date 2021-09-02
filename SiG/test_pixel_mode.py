#!/usr/bin/env python

import os
import sys
import time
import usb.core
import platform
import argparse
import matplotlib.pyplot as plt

VID             = 0x24aa
PID             = 0x4000
BUF             = [0] * 8
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
TIMEOUT_MS      = 1000

def get_spectrum():
    print("sending ACQUIRE")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

    bytes_to_read = args.pixels * 2
    print(f"reading {bytes_to_read} bytes from bulk endpoint")
    data = dev.read(0x82, bytes_to_read) 

    if len(data) != bytes_to_read:
        print("ERROR: read %d bytes" % len(data))
        sys.exit(1)

    spectrum = []
    for i in range(args.pixels):
        spectrum.append(data[i*2] | (data[i*2 + 1] << 8))

    return spectrum

################################################################################
# parse command-line arguments
################################################################################

parser = argparse.ArgumentParser()
parser.add_argument("--integration-time-ms", type=int, default=400, help="default 400")
parser.add_argument("--gain-db",             type=int, default=8, help="default 8")
parser.add_argument("--count",               type=int, default=1, help="how many spectra to take")
parser.add_argument("--delay-ms",            type=int, default=10, help="pause between throwaways (default 10)")
parser.add_argument("--pixels",              type=int, default=1920, help="default 1920")
parser.add_argument("--pixel-mode",          type=int, default=None, choices=[0,1,2,3], help="(optional, no default)")
parser.add_argument("--plot",                action="store_true", help="display graph")
parser.add_argument("--outfile",             type=str, help="save spectra")
args = parser.parse_args()

################################################################################
# connect
################################################################################

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print(f"No matching spectrometer found (VID 0x{VID:04x}, PID 0x{PID:04x})")
    sys.exit(1)

if os.name == "posix":
    dev.set_configuration()
    usb.util.claim_interface(dev, 0)

# print(dev)

################################################################################
# set acquisition parameters
################################################################################

print("sending SET_INTEGRATION_TIME_MS -> %d ms" % args.integration_time_ms)
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, args.integration_time_ms, 0, BUF, TIMEOUT_MS)

gain_ff = args.gain_db << 8
print(f"sending GAIN_DB -> {args.gain_db} (FunkyFloat 0x{gain_ff:04x})")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gain_ff, 0, BUF, TIMEOUT_MS) 

if args.pixel_mode is not None:
    print(f"setting pixel mode {args.pixel_mode}")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xfd, args.pixel_mode, 0, BUF, TIMEOUT_MS)
    print("sleeping 1 sec for pixel mode to 'take'")
    time.sleep(1)

################################################################################
# collect spectra
################################################################################

spectra = []
for i in range(args.count):
    if i > 0:
        print(f"sleeping {args.delay_ms}ms")
        time.sleep(args.delay_ms / 1000.0)
    spectrum = get_spectrum()
    spectra.append(spectrum)

################################################################################
# process spectra
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
    plt.title(f"integration time {args.integration_time_ms}ms, gain {args.gain_db}dB, pixel mode {args.pixel_mode}, count {args.count}")
    plt.show()
