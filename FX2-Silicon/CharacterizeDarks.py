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
    with open("characterized_darks.csv", "w") as f:
        for exp in range(args.bits):
            integration_time_ms = 2 ** (exp + 1) - 1

            log("setting integration time = %d ms (%d bits)" % (integration_time_ms, exp + 1))
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
parser.add_argument("--bits", type=int, default=10, help="max integration time in bits (default 10, max 24)")
args = parser.parse_args()

dev = usb.core.find(idVendor=0x24aa, idProduct=int(args.pid, 16))
if not dev:
    print "No spectrometers found"
    sys.exit()

characterize_dark()
