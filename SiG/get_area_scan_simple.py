import os
import png
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
LINES = 1080
CSVFILE = "area_scan.csv"
PNGFILE = "area_scan.png"

dev = None

def send_code(cmd, value=0, index=0, buf=BUF, timeout=TIMEOUT_MS):
    print("DEBUG: sending HOST_TO_DEVICE cmd 0x%02x, value 0x%04x, index 0x%04x, buf %s, timeout %d\n" % (
        cmd, value, index, buf, timeout))
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, timeout)

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

# print(dev)

print("Enabling area scan")
send_code(0xeb, 1)

# initialize CSV
print(f"Recording to {CSVFILE}")
if os.path.exists(CSVFILE):
    os.remove(CSVFILE)

# initialize PNG
image = [[0 for _ in range(PIXELS)] for _ in range(LINES)]

for i in range(LINES):
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
    spectrum[0] = i
    print(f"read spectrum {i}/{LINES}: {spectrum[:10]}")

    sleep(0.2)

    with open(CSVFILE, "a") as csvfile:
        csvfile.write(", ".join([f"{pixel}" for pixel in spectrum]) + "\n")

    # stomp endpoints so they don't skew image intensity range
    line_num = spectrum[0] # capture this before stomping
    for j in range(3):
        spectrum[j] = spectrum[3]
    spectrum[-1] = spectrum[-2]

    image[line_num] = spectrum

print("Exiting area scan")
send_code(0xeb, 0)

# normalize to 9-bit, then clamp to 8-bit (brightens image)
# (probably some clever Numpy way to do this)
hi = max([max(line) for line in image])
for y in range(LINES):
    for x in range(PIXELS):
        image[y][x] = min(255, int((512.0 * image[y][x] / hi)))

# save PNG file
print(f"Saving {PNGFILE}")
with open(PNGFILE, 'wb') as pngfile:
    png_writer = png.Writer(width=PIXELS, height=LINES)
    png_writer.write(pngfile, image)
