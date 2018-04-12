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
    print "No spectrometer found."
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

SAMPLES_PER_PULSE   = 100   # Amount of samples to acquire per stage/increment
SAMPLING_PERIOD_SEC = 0.2   # Time in between each sample
NUMBER_OF_PULSES    = 3     # Number of test pulses 
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
        print 'Set {0:x}  Fail'.format(SetCommand)
    else:
        RetValue = Get_Value(GetCommand, RetLen)
        if SetValue == RetValue:
            # print 'Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue)
            return True
        else:
            print 'Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue)
    return False

def Ramp_Laser(current_laser_setpoint, target_laser_setpoint, increments):
    timeStart = datetime.datetime.now()
    laser_setpoint = current_laser_setpoint + 0.0

    # Determine laser stepsize based on inputs
    if current_laser_setpoint < target_laser_setpoint:
        counter_laser_stepsize = (float(target_laser_setpoint) - float(current_laser_setpoint)) / float(increments)
    else:
        counter_laser_stepsize = (float(current_laser_setpoint) - float(target_laser_setpoint)) / float(increments)                
    print "Ramp_Laser: counter_laser_stepsize = %.2f" % counter_laser_stepsize

    # Setup our modulation scheme and start at current point
    Test_Set(SET_LASER_MOD_PERIOD,      GET_LASER_MOD_PERIOD, 100, 5) # Sets the modulation period to 100us
    Test_Set(SET_LASER_MOD_PULSE_WIDTH, GET_LASER_MOD_PULSE_WIDTH, int(current_laser_setpoint), 5)
    Test_Set(SET_LASER_ENABLE,          GET_LASER_ENABLE, 1, 1)

    # Apply first x% of the jumpjump. Bounding is not needed, but done anyway
    if (current_laser_setpoint < target_laser_setpoint):
        laser_setpoint = min(target_laser_setpoint, (float(laser_setpoint) + (RAMP_SKIP_PERCENT * increments * float(counter_laser_stepsize))))
    else:
        laser_setpoint = max(target_laser_setpoint, (float(laser_setpoint) - (RAMP_SKIP_PERCENT * increments * float(counter_laser_stepsize))))

    # Skip the first portion and start at RAMP_SKIP_PERCENT% of the way through the increments
    initial_step = int(RAMP_SKIP_PERCENT * increments)
    step = initial_step
    while step < increments:

        # Increment ramping counter
        step += 1

        # Apply based on direction and bound based on inputs
        if current_laser_setpoint < target_laser_setpoint:
            laser_setpoint = min(target_laser_setpoint, float(laser_setpoint) + float(counter_laser_stepsize))
        else:
            laser_setpoint = max(target_laser_setpoint, float(laser_setpoint) - float(counter_laser_stepsize))

        # Apply value to system
        Test_Set(SET_LASER_MOD_PULSE_WIDTH, GET_LASER_MOD_PULSE_WIDTH, int(laser_setpoint), 5)

        # This first part of the IF statement is never reached.
        # testing has shown that the lead-in to 80% can be instantaneous.
        # Only the last ~20% needs rounding
        if step + 1 > increments:
            delay_sec = 0
        else:                        
            # pro-rate delay such that it starts short, and lengthens as you approach the final step
            steps_undertaken = step - initial_step
            # delay_sec = 0.01 + 0.02 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 2.00) # 10.4sec
            # delay_sec = 0.01 + 0.20 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.50) # 27.3 sec
            # delay_sec = 0.01 + 0.10 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.30) # 8.5 sec
            # delay_sec = 0.01 + 0.08 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.20) # 5.5sec, overshoot
            # delay_sec = 0.01 + 0.05 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.30) # 4.5sec, overshoot
            # delay_sec = 0.01 + 0.03 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.40) # 3.6sec, overshoot
            # delay_sec = 0.00 + 0.09 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.25) # 6.7sec
            # delay_sec = 0.00 + 0.08 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.25) # 6.0sec, decent?
            # delay_sec = 0.00 + 0.08 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.25) # 4.7sec w/90, small overshoot? 
            # delay_sec = 0.00 + 0.08 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.30) # 4.0sec w/80, small overshoot (points 146-182 = 3.6 sec...this may be okay?)
            # delay_sec = 0.00 + 0.10 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.50) # 3.8sec w/60, overshoot
            # delay_sec = 0.00 + 0.10 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.40) # 4.5sec w/70, overshoot
            # delay_sec = 0.00 + 0.08 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.30) # 6.8sec w/100
            # delay_sec = 0.00 + 0.08 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.30) # 4.1sec w/80, 125-215 = 9sec?

            delay_sec = 0.00 + 0.08 * (1 - RAMP_SKIP_PERCENT) * pow(steps_undertaken, 1.30) 

        print "Ramp_Laser: step = %3d, laser_setpoint = %8.2f, delay_sec = %8.3f" % (step, laser_setpoint, delay_sec)
        sleep(delay_sec)

    timeEnd = datetime.datetime.now()
    print "Ramp_Laser: ramp time %.3f sec" % (timeEnd - timeStart).total_seconds()

############################################################################################
# First stage of testing will perform 100% laser power pulses using a ramping routine
# to reach the 100% threshold
############################################################################################
print "Stage 1 - Ramping"
for PulseCounter in range(NUMBER_OF_PULSES):

    # Set laser power to maximum to begin pulsing
    print "Laser OFF",        Test_Set(SET_LASER_ENABLE,          GET_LASER_ENABLE, 0, 1)          # Turns the laser off
    print "Laser Mod ENABLE", Test_Set(SET_LASER_MOD_ENABLE,      GET_LASER_MOD_ENABLE, 1, 1)      # Disables modulation, this sets it to 100%
    print "Laser Mod Period", Test_Set(SET_LASER_MOD_PERIOD,      GET_LASER_MOD_PERIOD, 100, 5)    # Sets the modulation period to 100us
    print "Laser Mod PW",     Test_Set(SET_LASER_MOD_PULSE_WIDTH, GET_LASER_MOD_PULSE_WIDTH, 1, 5) # Sets the modulation pulse-width to 10us

    delay_sec = SAMPLES_PER_PULSE * SAMPLING_PERIOD_SEC

    print "sleeping %.2f" % delay_sec
    time.sleep(delay_sec)

    start = 1
    end   = 100
    steps = 80
    print "Ramping laser from %d to %d in %d steps" % (start, end, steps)
    Ramp_Laser(start, end, steps)

    print "sleeping %.2f" % delay_sec
    time.sleep(delay_sec)

############################################################################################
# This second stage of testing will perform the same function but disregards ramping
############################################################################################
if False:
    print "Stage 2 - Without Ramping"
    for PulseCounter in range(NUMBER_OF_PULSES):

        # Set laser power to maximum to begin pulsing
        print "Laser OFF",         Test_Set(SET_LASER_ENABLE,     GET_LASER_ENABLE,     0, 1) # Turns the laser off
        print "Laser Mod Disable", Test_Set(SET_LASER_MOD_ENABLE, GET_LASER_MOD_ENABLE, 0, 1) # Disables modulation, this sets it to 100%        

        for SamplingCounter in range(SAMPLES_PER_PULSE):
            print "Laser Temperature    ", Get_Value(GET_LASER_TEMPERATURE, 2)
            time.sleep(SAMPLING_PERIOD_SEC)

        # Set laser power to maximum to begin pulsing
        print "Laser Mod Disable", Test_Set(SET_LASER_MOD_ENABLE, GET_LASER_MOD_ENABLE, 0, 1) # Disables modulation, this sets it to 100%
        print "Laser ON",          Test_Set(SET_LASER_ENABLE,     GET_LASER_ENABLE,     1, 1) # Turns the laser off

        for SamplingCounter in range(SAMPLES_PER_PULSE):
            print "Laser Temperature    ", Get_Value(GET_LASER_TEMPERATURE, 2)
            time.sleep(SAMPLING_PERIOD_SEC)

# no matter what, turn off laser when done
print "Laser OFF ", Test_Set(SET_LASER_ENABLE, GET_LASER_ENABLE, 0, 1)
