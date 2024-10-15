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
VR_SET_LASER_POWER_ATTENUATION = 0x82


parser = argparse.ArgumentParser()
parser.add_argument("--attn", type=int, help="attenuation setpoint (0 to 255)")
args = parser.parse_args()

attnSetPoint = -1

#if args.attn is None:
#   print("specify attn setpoint (0 to 255) !!")
#   quit()
#
#if args.attn is not None:
#   attnSetPoint = args.attn
#   # print("attn setpoint ", attnSetPoint)
#   if attnSetPoint < 0 or attnSetPoint > 255:
#      print("attn setpoint range is 0 to 255 !!")
#      quit()

def send_cmd(cmd, value, index=0, buf=None):
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

def Get_Value(Command, command2, ByteCount, index=0):
    return dev.ctrl_transfer(DEVICE_TO_HOST, Command, command2, 0, ByteCount, TIMEOUT_MS)

def set_laser_pwr_attn_level(setPoint):
    # send_cmd(VR_SET_LASER_POWER_ATTENUATION, setPoint)
    cmd = VR_SET_LASER_POWER_ATTENUATION
    value = setPoint
    index = 0
    length = 1
    resp = dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
    print("resp is ", resp)
    if resp[0] == 0:
       print("laser pwr attn set to {}".format(setPoint))
    else:
       print("failed to set laser pwr attn - error code {}".format(resp[0]))
       
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
    #resp = dev.ctrl_transfer(DEVICE_TO_HOST, 0xfd, 0, 0, 0, TIMEOUT_MS)

send_acq_auto_raman_req(12345, 
                        321,
                        2,
                        567, 
                        14,
                        22,
                        1,
                        47890,
                        51234,
                        42876,
                        6,
                        400,
                        61234,
                        34)
# print("sent setpoint {} to unit".format(attnSetPoint))
