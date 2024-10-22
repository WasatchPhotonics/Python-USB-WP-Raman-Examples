#!/usr/bin/env python

import sys
import usb.core
import argparse

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

if not dev:
    print("No spectrometer found")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT_MS = 1000

parser = argparse.ArgumentParser()
parser.add_argument("--attn", type=int, help="attenuation setpoint (0 to 255)")
args = parser.parse_args()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

def send_acq_auto_raman_req(maxMS,
                            startIntegMS,
                            startGainDB,
                            maxIntegMS,
                            minIntegMS,
                            maxGainDB,
                            minGainDB,
                            tgtCounts,
                            maxCounts,
                            minCounts,
                            maxFactor,
                            dropFactor,
                            saturation,
                            maxAvg):
    buff = bytearray()

    # maxMS [2]
    byte = maxMS & 0xff
    buff.append(byte)
    byte = ((maxMS >> 8) & 0xff)
    buff.append(byte)

    # startIntegMS [2]
    byte = startIntegMS & 0xff
    buff.append(byte)
    byte = ((startIntegMS >> 8) & 0xff)
    buff.append(byte)

    # startGainDB [1]
    byte = startGainDB & 0xff
    buff.append(byte)

    # maxIntegMS  [2]
    byte = maxIntegMS & 0xff
    buff.append(byte)
    byte = ((maxIntegMS >> 8) & 0xff)
    buff.append(byte)

    # minIntegMS  [2]
    byte = minIntegMS & 0xff
    buff.append(byte)
    byte = ((minIntegMS >> 8) & 0xff)
    buff.append(byte)

    # maxGainDB [1]
    byte = maxGainDB & 0xff
    buff.append(byte)
    
    # minGainDB [1]
    byte = minGainDB & 0xff
    buff.append(byte)

    # tgtCounts [2]
    byte = tgtCounts & 0xff
    buff.append(byte)
    byte = ((tgtCounts >> 8) & 0xff)
    buff.append(byte)

    # maxCounts [2]
    byte = maxCounts & 0xff
    buff.append(byte)
    byte = ((maxCounts >> 8) & 0xff)
    buff.append(byte)

    # minCounts [2]
    byte = minCounts & 0xff
    buff.append(byte)
    byte = ((minCounts >> 8) & 0xff)
    buff.append(byte)
  
    # maxFactor [1]
    byte = maxFactor & 0xff
    buff.append(byte)
    
    # dropFactor (Encoded) [2]
    byte = dropFactor & 0xff
    buff.append(byte)
    byte = ((dropFactor >> 8) & 0xff)
    buff.append(byte)
    
    # saturation [2]
    byte = saturation & 0xff
    buff.append(byte)
    byte = ((saturation >> 8) & 0xff)
    buff.append(byte)

    # maxAvg [1]
    byte = maxAvg & 0xff
    buff.append(byte)

    print("params sz ", len(buff))

    send_cmd(0xfd, 0, 0, buff)

    ############################################################################
    # get spectrum
    ############################################################################

    bytes_to_read = 1952 * 2
    block_size = 64
    data = []
    print(f"trying to read {bytes_to_read} bytes in chunks of {block_size} bytes")
    while True:
        try:
            this_data = dev.read(0x82, block_size, timeout=1000)
            data.extend(this_data)
            if len(data) >= bytes_to_read:
                break
        except usb.core.USBTimeoutError as ex:
            print(".", end='')
    print()

    spectrum = []
    if data is not None:
        for i in range(0, len(data), 2):
            spectrum.append(data[i] | (data[i+1] << 8))
    print(", ".join([str(v) for v in spectrum]))

send_acq_auto_raman_req(
    maxMS        = 12345,       
    startIntegMS = 321,         
    startGainDB  = 2,           
    maxIntegMS   = 567,         
    minIntegMS   = 14,          
    maxGainDB    = 22,          
    minGainDB    = 1,           
    tgtCounts    = 47890,       
    maxCounts    = 51234,       
    minCounts    = 42876,       
    maxFactor    = 6,           
    dropFactor   = 400,         
    saturation   = 61234,       
    maxAvg       = 34)
