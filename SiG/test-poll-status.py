import os
import sys
import usb.core
import random
from datetime import datetime

from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000

PIXELS = 1952
COUNT  = 20

print(f"searching for spectrometer with VID 0x{VID:04x}, PID 0x{PID:04x}")
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

def get_poll_status():
    result = dev.ctrl_transfer(DEVICE_TO_HOST, 0xd4, 0, 0, BUF, TIMEOUT_MS)
    if result is not None:
        return int(result[0])

if os.path.exists("test.csv"):
    os.remove("test.csv")

int_time_ms = 400
gain_db = 8

# dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, int_time_ms, 0, BUF, TIMEOUT_MS)
# dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gain_db << 8, 0, BUF, TIMEOUT_MS)

for iteration in range(COUNT):
    print(f"\n=========== Iteration {iteration+1} of {COUNT} ============\n")
    if False:
        pass
    elif random.random() < 0.33:
        int_time_ms = random.randrange(100, 1000)
        print(f"setting integration time to {int_time_ms}ms")
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, int_time_ms, 0, BUF, TIMEOUT_MS)
    elif random.random() < 0.66:
        gain_db = random.randrange(0, 24)
        print(f"setting gain to {gain_db}db")
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, gain_db << 8, 0, BUF, TIMEOUT_MS)

    stable = True
    while not stable:
        print("waiting for stabilization...", end='')
        status = get_poll_status()
        print(f"status 0x{status:02x}")
        stable = 0 == status
        sleep(1)
    
    print("reading spectra")
    for i in range(COUNT):
        print(f"sending ACQUIRE {i+1:2d}/{COUNT}...", end='')
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

        print(f"reading {PIXELS}px...", end='')
        data = dev.read(0x82, PIXELS * 2) 

        if len(data) != PIXELS * 2:
            print(f"ERROR: read {len(data)} bytes")
            sys.exit(1)
        print(f"read {len(data)} bytes...", end='')

        spectrum = []
        for j in range(PIXELS):
            spectrum.append(data[j*2] | (data[j*2+1] << 8))
        lo = min(spectrum)
        hi = max(spectrum)
        avg = sum(spectrum)/PIXELS
        print(f"min {lo:5d}, max {hi: 5d}, avg {avg:8.2f}")

        # save data to outfile
        result = [ datetime.now(), iteration, int_time_ms, gain_db, lo, hi, avg ]
        result.extend(spectrum)
        with open("test.csv", "a") as outfile:
            outfile.write(",".join([str(value) for value in result]) + "\n")

        sleep(0.2)
