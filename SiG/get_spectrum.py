#!/usr/bin/env python

import os
import sys
import usb.core
import argparse
import platform
import matplotlib.pyplot as plt

from time import sleep
from datetime import datetime

VERSION         = "1.2"

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000
dev             = None

################################################################################
# function definitions
################################################################################

def poke(addr, values):
    buf = [ x for x in values ]
    while len(buf) < 8:
        buf.append(0)
    print(f"poking addr 0x{addr:02x} <- {buf}")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0x90, addr, len(buf), buf, TIMEOUT_MS)

def peek(addr, length):
    data = dev.ctrl_transfer(DEVICE_TO_HOST, 0x91, addr, 0, length, TIMEOUT_MS)
    print(f"peeking addr 0x{addr:02x} -> {data}")
    return data

def set_sensor_enable(flag):
    old = peek(0x20, 1)[0] # bit 0 enable, bit 1 reghold
    new = (old | 0x01) if flag else (old & 0xfe)
    poke(0x20, [new])

def wait_for_stability():
    print("waiting for stability...", end='')
    count = 0
    while True:
        status = get_poll_status()
        if 0 == status: # IDLE
            print("stable!")
            return True
        else:
            print(".", end='')
            if count > 30:
                print("giving up")
                return False
            count += 1
            sleep(1)

def get_poll_status():
    result = dev.ctrl_transfer(DEVICE_TO_HOST, 0xd4, 0, 0, 1, TIMEOUT_MS)
    if result is not None:
        return result[0]

################################################################################
# parse command-line arguments
################################################################################

parser = argparse.ArgumentParser()
parser.add_argument("--integration-time-ms", type=int)
parser.add_argument("--gain-db",             type=int)
parser.add_argument("--delay-ms",            type=int, default=10, help="how long to delay between spectra (default 10)")
parser.add_argument("--count",               type=int, default=1, help="how many spectra to take")
parser.add_argument("--pixels",              type=int, default=1952, help="default 1952")
parser.add_argument("--plot",                action="store_true", help="display graph")
parser.add_argument("--debug",               action="store_true", help="debug output")
parser.add_argument("--outfile",             type=str, help="save spectra")
args = parser.parse_args()

################################################################################
# connect
################################################################################

print(f"SiG/get_spectrum.py {VERSION}")
print("get_spectrum searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
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

if args.outfile is not None:
    with open(args.outfile, "w") as outfile:
        outfile.write("timestamp, delay_sec, int_time_ms, gain_db, avg, spectrum")

################################################################################
# configure
################################################################################

result = dev.ctrl_transfer(DEVICE_TO_HOST, 0xc0, 0, 0, 4, TIMEOUT_MS)
if result is not None and len(result) >= 4:
    print("Firmware version: %d.%d.%d.%d" % (result[3], result[2], result[1], result[0]))

################################################################################
# collect
################################################################################

delay_sec = 0
MAX_ERROR = 10
last_was_success = True

while True:
    set_sensor_enable(False) # toggle, per Vic
    set_sensor_enable(True)

    if args.integration_time_ms is not None:
        print("sending SET_INTEGRATION_TIME_MS -> %d ms" % args.integration_time_ms)
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, args.integration_time_ms, 0, BUF, TIMEOUT_MS)

        if not wait_for_stability():
            sys.exit(1)

    # if args.gain_db is not None:
    #     gainDB = args.gain_db << 8 
    #     print("sending GAIN_DB -> 0x%04x (FunkyFloat)" % gainDB)
    #     dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gainDB, 0, BUF, TIMEOUT_MS) 

    spectra = []
    errors = 0
    for i in range(args.count):
        print(f"{datetime.now()} sleeping {args.delay_ms}ms...", end='')
        sleep(args.delay_ms / 1000.0)

        print("sending ACQUIRE...", end='')
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

        print(f"reading {args.pixels}px...", end='')
        try:
            data = dev.read(0x82, args.pixels * 2) 
            last_was_success = True
        except:
            errors += 1
            last_was_success = False
            print(f"ERROR {errors}: waiting 5sec...", end='')
            sleep(5)
            if wait_for_stability():
                continue
            raise

        print(f"read {len(data)} bytes...", end='')
        if len(data) != args.pixels * 2:
            print("ERROR: read %d bytes" % len(data))
            sys.exit(1)

        spectrum = []
        for px in range(args.pixels):
            spectrum.append(data[px*2] | (data[px*2 + 1] << 8)) # demarshal LSB-MSB to uint16

        avg = sum(spectrum)/len(spectrum)
        print(f"avg {avg:8.2f}")

        spectra.append(spectrum)

        result = [ datetime.now(), delay_sec, args.integration_time_ms, args.gain_db, avg ]
        result.extend(spectrum)
        if args.outfile:
            with open(args.outfile, "a") as outfile:
                outfile.write(",".join([str(value) for value in result]) + "\n")

    if not last_was_success:
        break

    delay_sec += 5
    print(f"sleeping {delay_sec}sec...")
    sleep(delay_sec)

################################################################################
# process 
################################################################################

if args.plot:
    [plt.plot(a) for a in spectra]
    plt.title(f"integration time {args.integration_time_ms}ms, gain {args.gain_db}dB, count {args.count}, throwaways {args.throwaways}, delay {args.delay_ms}ms")
    plt.show()
