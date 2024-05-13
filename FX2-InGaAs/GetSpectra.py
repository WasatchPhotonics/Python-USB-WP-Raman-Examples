import usb.core
import datetime
import time
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
print(dev)

H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000
PIXELS=512

print("Start Data Acquisition")
dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition

print("Reading spectrum")
spectrum = []
data = dev.read(0x82, PIXELS * 2)
for i in range(0, len(data), 2):
    intensity = data[i] | (data[i+1] << 8) # pixels are little-endian uint16
    spectrum.append(intensity)

print("Spectrum:")
for i, intensity in enumerate(spectrum):
    print(f"pixel {i:3d}: {intensity}")
