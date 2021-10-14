#!/usr/bin/env python -u

import sys
import usb.core
from time import sleep

#import common

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000

VR_READ_CCD_TEMP = 0xd7
VR_FPGA_CONFIG= 0xB3
VR_GET_LASER_TEMP = 0xD5

NUM_WRECK_ITS = 100
buf = [0] * 2

dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)

if not dev:
    print("No spectrometers found")
    sys.exit()

# Read FPGA Config
result = dev.ctrl_transfer(DEVICE_TO_HOST, VR_FPGA_CONFIG, 0, 0, buf, TIMEOUT_MS)
print("Starting FPGA CONFIG REG: 0x%04x" % (result[1] << 8 | result[0]))   

# Wreck it
for num in range(1, NUM_WRECK_ITS):
    # Read Laser Temp
    result = dev.ctrl_transfer(DEVICE_TO_HOST, VR_GET_LASER_TEMP, 0, 0, buf, TIMEOUT_MS)

    # Read FPGA Config
    result = dev.ctrl_transfer(DEVICE_TO_HOST, VR_FPGA_CONFIG, 0, 0, buf, TIMEOUT_MS)
    fpga_config_reg = result[1] << 8 | result[0]

    # Write FPGA Config (write back what we just read)
    dev.ctrl_transfer(HOST_TO_DEVICE, VR_FPGA_CONFIG, fpga_config_reg, 0, buf, TIMEOUT_MS)

    # Read CCD TEMP
    result = dev.ctrl_transfer(DEVICE_TO_HOST, VR_READ_CCD_TEMP, 0, 0, buf, TIMEOUT_MS)

# Read FPGA Config
result = dev.ctrl_transfer(DEVICE_TO_HOST, VR_FPGA_CONFIG, 0, 0, buf, TIMEOUT_MS)
print("Ending FPGA CONFIG REG: 0x%04x" % (result[1] << 8 | result[0]))   