#!/usr/bin/env python -u

import usb.core
import datetime
import argparse
import random
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
    print("%s %s" % (now, msg))

def test_integration_time():
    count = 0
    with open("integration_time_test.csv", "w") as f:
        while True:
            integration_time_ms = random.randint(args.min, args.max)
            count += 1

            log("setting integration time = %d ms" % integration_time_ms)
            send_cmd(0xb2, integration_time_ms)

            timeout_ms = integration_time_ms * 2 + 100
            log("  starting acquisition (timeout_ms %d)" % timeout_ms)

            start = datetime.datetime.now()
            spectrum = get_spectrum(timeout_ms=timeout_ms)
            end = datetime.datetime.now()

            elapsed_sec = (end - start).total_seconds()
            log("  acquisition completed in %.3f sec" % elapsed_sec)

            f.write("%s, %d, %.2f, " % (datetime.datetime.now(), integration_time_ms, elapsed_sec))
            f.write(",".join(["%.2f" % x for x in spectrum]))
            f.write("\n")

parser = argparse.ArgumentParser()
parser.add_argument("--pid", default="1000", choices=["1000", "2000", "4000"], help="USB Product ID (hex) (default 1000)")
parser.add_argument("--pixels", type=int, default=1024, help="spectrometer pixels (default 1024)")
parser.add_argument("--min", type=int, default=10, help="min integration time (ms) (default 10)")
parser.add_argument("--max", type=int, default=20000, help="max integration time (ms) (default 20000)")
args = parser.parse_args()

dev = usb.core.find(idVendor=0x24aa, idProduct=int(args.pid, 16))
if not dev:
    print("No spectrometers found")
    sys.exit()

test_integration_time()
