import sys
import datetime
import usb.core

from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000

PIXELS = 1952
COUNT  = 10

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

print(dev)

INT_TIME_MS = 50
print(f"setting integration time to {INT_TIME_MS}ms")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb2, INT_TIME_MS, 0, BUF, TIMEOUT_MS)

GAIN_DB = 0
print(f"setting gain dB to {GAIN_DB}dB")
dev.ctrl_transfer(HOST_TO_DEVICE, 0xb7, GAIN_DB << 8, 0, BUF, TIMEOUT_MS)

with open("spectra.csv", "w") as f:
    for i in range(COUNT):
        now = datetime.datetime.now()

        print(f"{now} sending ACQUIRE")
        dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

        print(f"reading {PIXELS} from bulk endpoint")
        data = dev.read(0x82, PIXELS * 2) 

        print(f"read {len(data)} bytes")
        if len(data) != PIXELS * 2:
            print("ERROR: read %d bytes" % len(data))
            sys.exit(1)

        spectrum = []

        for j in range(0, len(data), 2):
            lsb = data[j]
            msb = data[j+1]
            spectrum.append((msb << 8) | lsb)

        print(f"read data {i}/{COUNT}: {data[:10]}")
        f.write("data, " + " ".join([f"{x:02x}" for x in data]) + "\n")
        f.write("spectrum, " + ", ".join([f"{x}" for x in spectrum]) + "\n")

        sleep(0.2)
