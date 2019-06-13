#!/usr/bin/env python -u

import usb.core
import datetime
import argparse
import sys

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
TIMEOUT_MS = 1000
ZZ = [0] * BUFFER_SIZE

args = None
dev = None

def send_cmd(cmd, uint40):
    lsw   = (uint40      ) & 0xffff
    msw   = (uint40 >> 16) & 0xffff
    ZZ[0] = (uint40 >> 32) & 0xff
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, lsw, msw, ZZ, TIMEOUT_MS)

def get_spectrum(timeout_ms=TIMEOUT_MS):
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, ZZ, timeout_ms)
    data = dev.read(0x82, args.pixels * 2, timeout=timeout_ms)
    spectrum = []
    for i in range(0, len(data), 2):
        spectrum.append(float(data[i] | (data[i+1] << 8))) # LSB-MSB
    return spectrum

def log(msg=""):
    now = datetime.datetime.now()
    print "%s %s" % (now, msg)

def characterize_dark():
    step = 0
    with open("characterized_darks.csv", "w") as f:
        while True:
            if args.exponential:
                integration_time_ms = 2 ** (step + 1) - 1
            else:
                integration_time_ms = args.min + args.incr * step

            if integration_time_ms > args.max:
                break

            step += 1

            for i in range(args.reps):

                log("setting integration time = %d ms" % integration_time_ms)
                send_cmd(0xb2, integration_time_ms)

                timeout_ms = integration_time_ms * 2 + 100
                log("  starting acquisition (timeout_ms %d)" % timeout_ms)

                start = datetime.datetime.now()
                spectrum = get_spectrum(timeout_ms=timeout_ms)
                end = datetime.datetime.now()

                elapsed_sec = (end - start).total_seconds()
                log("  acquisition completed in %.3f sec" % elapsed_sec)

                log("  min = %.2f" % min(spectrum))
                log("  avg = %.2f" % (sum(spectrum) / len(spectrum)))
                log("  max = %.2f" % max(spectrum))
                log()

                f.write("%d," % integration_time_ms)
                f.write(",".join(["%.2f" % x for x in spectrum]))
                f.write("\n")

parser = argparse.ArgumentParser()
parser.add_argument("--pid", default="1000", choices=["1000", "2000", "4000"], help="USB Product ID (hex) (default 1000)")
parser.add_argument("--count", type=int, default=1000, help="how many spectra to read (default 1000)")
parser.add_argument("--pixels", type=int, default=1024, help="spectrometer pixels (default 1024)")
parser.add_argument("--min", type=int, default=1, help="min integration time (ms) (default 1)")
parser.add_argument("--max", type=int, default=1000, help="max integration time (ms) (default 1000)")
parser.add_argument("--reps", type=int, default=1, help="repeats per integration time (default 1)")
parser.add_argument("--incr", type=int, default=100, help="integration time increment (default 1)")
parser.add_argument("--exponential", action='store_true', help="increase integration time exponentially (2^n - 1)")
args = parser.parse_args()

dev = usb.core.find(idVendor=0x24aa, idProduct=int(args.pid, 16))
if not dev:
    print "No spectrometers found"
    sys.exit()

characterize_dark()
