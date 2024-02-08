import sys
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

for i in range(COUNT):
    print("sending ACQUIRE")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

    print(f"reading {PIXELS} from bulk endpoint")
    data = dev.read(0x82, PIXELS * 2) 

    print(f"read {len(data)} bytes")
    if len(data) != PIXELS * 2:
        print("ERROR: read %d bytes" % len(data))
        sys.exit(1)

    spectrum = []
    for j in range(PIXELS):
        spectrum.append(data[j] | (data[j+1] << 8))
    print(f"read spectrum {i}/{COUNT}: {spectrum[:10]}")

    sleep(0.2)
