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

def get_spectrum():
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, ZZ, TIMEOUT_MS)
    data = dev.read(0x82, args.pixels * 2)
    spectrum = []
    for i in range(0, len(data), 2):
        spectrum.append(data[i] | (data[i+1] << 8)) # LSB-MSB
    return spectrum

def timing_test():
    # set integration time
    send_cmd(0xb2, args.integration_time_ms)

    last_total = 0
    start = datetime.datetime.now()
    for i in range(args.count):
        spectrum = get_spectrum()

        # make sure we're really reading distinct spectra
        total = sum(spectrum)
        if total == last_total:
            print "Warning: consecutive spectra summed to %d" % total
        last_total = total

        if i and i % 100 == 0:
            print "%s read %d spectra" % (datetime.datetime.now(), i)

    end = datetime.datetime.now()

    # measure observed time
    elapsed_sec = (end - start).total_seconds()
    scan_rate = float(args.count) / elapsed_sec

    # compare vs theoretical time
    integration_total_sec = args.count * args.integration_time_ms * 0.001
    comms_total_sec = elapsed_sec - integration_total_sec
    comms_average_ms = (comms_total_sec / args.count) * 1000.0

    print "\nread %d spectra at %d ms in %.2f sec\n" % (args.count, args.integration_time_ms, elapsed_sec)
    print "scan rate              = %6.2f spectra/sec" % scan_rate
    print "cumulative integration = %6.2f sec" % integration_total_sec
    print "cumulative overhead    = %6.2f sec" % comms_total_sec
    print "comms latency          = %6.2f ms/spectrum" % comms_average_ms

parser = argparse.ArgumentParser()
parser.add_argument("--pid", default="1000", choices=["1000", "2000", "4000"], help="USB Product ID (hex) (default 1000)")
parser.add_argument("--count", type=int, default=1000, help="how many spectra to read (default 1000)")
parser.add_argument("--pixels", type=int, default=1024, help="spectrometer pixels (default 1024)")
parser.add_argument("--integration-time-ms", type=int, default=1, help="integration time (ms) (default 1)")
args = parser.parse_args()

dev = usb.core.find(idVendor=0x24aa, idProduct=int(args.pid, 16))
if not dev:
    print "No spectrometers found"
    sys.exit()

timing_test()
