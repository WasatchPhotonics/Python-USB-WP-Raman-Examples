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

def uint16_to_little_endian(values):
    a = []      
    for n in values:
        a.append(n & 0xff)          # lsb
        a.append((n >> 8) & 0xff)   # msb
    return a

def split(self, spectrum, widths):
	print(f"splitting spectrum of {len(spectrum)} pixels into {len(widths)} subspectra")
	subspectra = []
	start = 0
	for width in widths:
		end = start + width
		if end > len(spectrum):
			logger.error(f"computed end {end} of width {width} overran colleted spectrum")
			return None
		subspectrum = spectrum[start:end]
		subspectra.append(subspectrum)
		start = end
	return subspectra

################################################################################
# parse command-line arguments
################################################################################

parser = argparse.ArgumentParser()
parser.add_argument("--integration-time-ms", type=int, default=400, help="default 400")
parser.add_argument("--gain-db",             type=int, default=8, help="default 8")
parser.add_argument("--count",               type=int, default=1, help="how many spectra to take")
parser.add_argument("--delay-ms",            type=int, default=10, help="pause between throwaways (default 10)")
parser.add_argument("--region",              type=str, action="append", help="region, y0, y1, x0, x1")
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

################################################################################
# set acquisition parameters
################################################################################

print("sending SET_INTEGRATION_TIME_MS -> %d ms" % args.integration_time_ms)
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, args.integration_time_ms, 0, BUF, TIMEOUT_MS)

gain_ff = args.gain_db << 8
print(f"sending GAIN_DB -> {args.gain_db} (FunkyFloat 0x{gain_ff:04x})")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gain_ff, 0, BUF, TIMEOUT_MS) 

widths = []
if args.region is not None:
	num, y0, y1, x0, x1 = [int(x) for x in region.split(',')]
	buf = uint16_to_little_endian([y0, y1, x0, x1])
	width = x1 - x0 + 1
	widths.append(width)
	print(f"configuring region {num} to coords ({y0}, {y1}, {x0}, {x1} (width {width}, buf {buf}")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0x25, num, buf, TIMEOUT_MS)
    print("sleeping 1 sec for detector region to 'take'")
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

if args.outfile:
    print(f"writing {args.outfile}")
    with open(args.outfile, 'w') as f:
		for spectrum in spectra:
			subspectra = split(spectrum, widths)
			for i in range(len(subspectra)):
				subspectrum = subspectra[i]
				f.write("spectrum %d, %s" % (i, ', '.join([str(x) for x in subspectrum])))
                if i + 1 < len(subspectra):
                    f.write(", end_of_subspectrum")
            f.write("\n")
            
if args.plot:
    [[plt.plot(a) for a in split(spectrum, widths)] for spectrum in spectra]
    plt.title(f"integration time {args.integration_time_ms}ms, gain {args.gain_db}dB, widths {widths}, count {args.count}")
    plt.show()