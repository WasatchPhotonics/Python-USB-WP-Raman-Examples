#!/usr/bin/env python -u

import sys
import usb.core
import datetime
import time
from time import sleep

VID = 0x24aa
PID = 0x1000
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No spectrometer found.")
    sys.exit()

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000
BUFFER_SIZE = 8
ZZ = [0] * BUFFER_SIZE

SET_LASER_ENABLE          = 0xbe
GET_LASER_ENABLE          = 0xe2
SET_LASER_MOD_ENABLE      = 0xbd
GET_LASER_MOD_ENABLE      = 0xe3
SET_LASER_MOD_PERIOD      = 0xc7
GET_LASER_MOD_PERIOD      = 0xcb
SET_LASER_MOD_PULSE_WIDTH = 0xdb
GET_LASER_MOD_PULSE_WIDTH = 0xdc
GET_LASER_TEMPERATURE     = 0xd5

SAMPLES_PER_PULSE   = 150   # Amount of samples to acquire per stage/increment
SAMPLING_PERIOD_SEC = 0.2   # Time in between each sample
NUMBER_OF_PULSES    = 2     # Number of test pulses 
RAMP_SKIP_PERCENT   = 0.80  # skip (don't ramp) first 80% of the delta in power (don't increase this)

def Get_Value(Command, ByteCount, index=0):
    RetVal = 0
    RetArray = dev.ctrl_transfer(DEVICE_TO_HOST, Command, 0, 0, ByteCount, TIMEOUT_MS)
    for i in range (0, ByteCount):
        RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
    return RetVal

def Test_Set(SetCommand, GetCommand, SetValue, RetLen):
    SetValueHigh = SetValue / 0x10000
    SetValueLow  = SetValue & 0xFFFF
    FifthByte = (SetValue >> 32) & 0xFF
    ZZ[0] = FifthByte
    Ret = dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT_MS)

    # MZ why delay 10ms after a write?
    sleep(0.01) # Time in seconds. 

    if BUFFER_SIZE != Ret:
        print('Set {0:x}  Fail'.format(SetCommand))
    else:
        RetValue = Get_Value(GetCommand, RetLen)
        if SetValue == RetValue:
            # print 'Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue)
            return True
        else:
            print('Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))
    return False

def Ramp_Laser(current_laser_setpoint, target_laser_setpoint, increments):

    timeStart = datetime.datetime.now()

    LUT = []
    MAX_X3 = increments * increments * increments 
    for x in range(increments, 0, -1):
        LUT.append(float(MAX_X3 - (x * x * x)) / 1000000.0)

    # Setup our modulation scheme and start at current point
    Test_Set(SET_LASER_MOD_PERIOD,      GET_LASER_MOD_PERIOD, 100, 5) # Sets the modulation period to 100us
    Test_Set(SET_LASER_MOD_PULSE_WIDTH, GET_LASER_MOD_PULSE_WIDTH, int(current_laser_setpoint), 5)
    Test_Set(SET_LASER_ENABLE,          GET_LASER_ENABLE, 1, 1)

    # apply first 80% jump
    if current_laser_setpoint < target_laser_setpoint:
        laser_setpoint = ((float(target_laser_setpoint) - float(current_laser_setpoint)) / 100.0) * 80.0
        laser_setpoint += float(current_laser_setpoint)
        eighty_percent_start = laser_setpoint
    else:
        laser_setpoint = ((float(laser_setpoint)-float(target_laser_setpoint)) / 100.0) * 80.0
        laser_setpoint = float(current_laser_setpoint) - laser_setpoint
        eighty_percent_start = laser_setpoint

    Test_Set(SET_LASER_MOD_PULSE_WIDTH, GET_LASER_MOD_PULSE_WIDTH, int(eighty_percent_start), 5)
    sleep(0.02)

    for counter_laser_setpoint in range(increments):
        lut_value = LUT[counter_laser_setpoint]
        target_loop_setpoint = eighty_percent_start \
                             + (lut_value * (float(target_laser_setpoint) - eighty_percent_start))

        width = int(target_loop_setpoint)
        Test_Set(SET_LASER_MOD_PULSE_WIDTH, GET_LASER_MOD_PULSE_WIDTH, width, 5)

        print("Ramp_Laser: step = %3d, width = 0x%04x, target_loop_setpoint = %8.2f" % (counter_laser_setpoint, width, target_loop_setpoint))
        sleep(0.01)

    timeEnd = datetime.datetime.now()
    print("Ramp_Laser: ramp time %.3f sec" % (timeEnd - timeStart).total_seconds())

############################################################################################
# First stage of testing will perform 100% laser power pulses using a ramping routine
# to reach the 100% threshold
############################################################################################
print("Stage 1 - Ramping")
for PulseCounter in range(NUMBER_OF_PULSES):

    # Set laser power to maximum to begin pulsing
    print("Laser OFF",        Test_Set(SET_LASER_ENABLE,          GET_LASER_ENABLE, 0, 1))          # Turns the laser off
    print("Laser Mod ENABLE", Test_Set(SET_LASER_MOD_ENABLE,      GET_LASER_MOD_ENABLE, 1, 1))      # Disables modulation, this sets it to 100%
    print("Laser Mod Period", Test_Set(SET_LASER_MOD_PERIOD,      GET_LASER_MOD_PERIOD, 100, 5))    # Sets the modulation period to 100us
    print("Laser Mod PW",     Test_Set(SET_LASER_MOD_PULSE_WIDTH, GET_LASER_MOD_PULSE_WIDTH, 1, 5)) # Sets the modulation pulse-width to 10us

    delay_sec = SAMPLES_PER_PULSE * SAMPLING_PERIOD_SEC

    print("sleeping %.2f" % delay_sec)
    time.sleep(delay_sec)

    start = 0
    end   = 100
    steps = 100
    print("Ramping laser from %d to %d in %d steps" % (start, end, steps))
    Ramp_Laser(start, end, steps)

    print("sleeping %.2f" % delay_sec)
    time.sleep(delay_sec)

############################################################################################
# This second stage of testing will perform the same function but disregards ramping
############################################################################################
if False:
    print("Stage 2 - Without Ramping")
    for PulseCounter in range(NUMBER_OF_PULSES):

        # Set laser power to maximum to begin pulsing
        print("Laser OFF",         Test_Set(SET_LASER_ENABLE,     GET_LASER_ENABLE,     0, 1)) # Turns the laser off
        print("Laser Mod Disable", Test_Set(SET_LASER_MOD_ENABLE, GET_LASER_MOD_ENABLE, 0, 1)) # Disables modulation, this sets it to 100%        

        for SamplingCounter in range(SAMPLES_PER_PULSE):
            print("Laser Temperature    ", Get_Value(GET_LASER_TEMPERATURE, 2))
            time.sleep(SAMPLING_PERIOD_SEC)

        # Set laser power to maximum to begin pulsing
        print("Laser Mod Disable", Test_Set(SET_LASER_MOD_ENABLE, GET_LASER_MOD_ENABLE, 0, 1)) # Disables modulation, this sets it to 100%
        print("Laser ON",          Test_Set(SET_LASER_ENABLE,     GET_LASER_ENABLE,     1, 1)) # Turns the laser off

        for SamplingCounter in range(SAMPLES_PER_PULSE):
            print("Laser Temperature    ", Get_Value(GET_LASER_TEMPERATURE, 2))
            time.sleep(SAMPLING_PERIOD_SEC)

# no matter what, turn off laser when done
print("Laser OFF ", Test_Set(SET_LASER_ENABLE, GET_LASER_ENABLE, 0, 1))
