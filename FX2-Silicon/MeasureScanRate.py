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

def send_cmd(cmd, uint40, RetLen):
    lsb  = (uint40 & 0xffff)
    msb  = (uint40 >> 16) & 0xffff
    ZZ[0] = (uint40 >> 32) & 0xff
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, lsb, msb, ZZ, TIMEOUT_MS)

def get_spectrum():
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, ZZ, TIMEOUT_MS)
    data = dev.read(0x82, args.pixels*2)
    spectrum = []
    for j in range (0, (args.pixels*2)/32, 1):
        for i in range (0, 31, 2):
            spectrum.append(data[j*32+i+1] << 8 | data[j*32+i])
    return spectrum

def timing_test():
    print "setting integration time to %d ms" % args.integration_time_ms
    send_cmd(0xb2, args.integration_time_ms, 6) # set integration time 1ms

    last_total = 0
    start = datetime.datetime.now()
    for i in range(args.count):
        spectrum = get_spectrum()

        # make sure we're really reading distinct spectra
        total = sum(spectrum)
        if total == last_total:
            print "Warning: consecutive spectra summed to %d" % total
        last_total = total

        if i % 100 == 0:
            print "%s read %d spectra" % (datetime.datetime.now(), i)

    end = datetime.datetime.now()

    elapsed_sec = (end - start).total_seconds()
    scan_rate = float(args.count) / elapsed_sec

    integration_total_sec = 0.001 * args.count * args.integration_time_ms
    comms_total_sec = elapsed_sec - integration_total_sec
    comms_average_ms = (comms_total_sec / args.count) * 1000.0

    print "read %d spectra in %.2f sec (%.2f spectra/sec)" % (args.count, elapsed_sec, scan_rate)
    print "comms latency = %.2f ms" % comms_average_ms

parser = argparse.ArgumentParser()
parser.add_argument("--pid", default="1000", choices=["1000", "2000", "4000"], help="USB Product ID (hex)")
parser.add_argument("--count", type=int, default=1000, help="how many spectra to read")
parser.add_argument("--pixels", type=int, default=1024, help="spectrometer pixels (default 1024)")
parser.add_argument("--integration-time-ms", type=int, default=1, help="integration time (ms)")
args = parser.parse_args()

dev = usb.core.find(idVendor=0x24aa, idProduct=int(args.pid, 16))
if not dev:
    print "No spectrometers found"
    sys.exit()

timing_test()
