#!/usr/bin/env python
"""
    This script uses matplotlib to graph a series of spectra taken at different 
    integration times.
"""

import usb.core
import usb.util
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from time import sleep

# select product
dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
BUFFER_SIZE    = 8
ZZ             = [0] * BUFFER_SIZE
TIMEOUT_MS     = 1000
PIXEL_COUNT    = 1024

def Get_Value(Command, ByteCount):
    try:
        RetVal = 0
        RetArray = dev.ctrl_transfer(0xC0, Command, 0, 0, ByteCount, TIMEOUT_MS)
        for i in range (0, ByteCount):
            RetVal = RetVal*256 + RetArray[ByteCount - i - 1]
        return RetVal
    except Exception as e:
        print(("Get Value fail", str(e)))


def Test_Set(SetCommand, GetCommand, SetValue, RetLen):
    try:
        SetValueLow  =  SetValue        & 0xffff
        SetValueHigh = (SetValue >> 16) & 0xffff
        FifthByte    = (SetValue >> 32) & 0xff
        ZZ[0] = FifthByte
        Ret = dev.ctrl_transfer(HOST_TO_DEVICE, SetCommand, SetValueLow, SetValueHigh, ZZ, TIMEOUT_MS)
        
        if BUFFER_SIZE != Ret:
            return ('Set {0:x}Fail'.format(SetCommand))
        else:
            RetValue = Get_Value(GetCommand, RetLen)
            if SetValue == RetValue:
                return ('Get {0:x} Success. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))
            else:
                return ('Get {0:x} Failure. Txd:0x{1:x} Rxd:0x{2:x}'.format(GetCommand, SetValue, RetValue))
    except Exception as e:
        print(("Test_Set fail", str(e)))

# Function gets a spectrum from the detector
def get_spectrum():
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, ZZ, TIMEOUT_MS) # trigger an acquisition
    data = dev.read(0x82, PIXEL_COUNT * 2)
     
    spectrum = []
    for i in range(0, len(data), 2):
        pixel = data[i] | (data[i+1] << 8) # LSB-MSB
        spectrum.append(pixel)
    return spectrum

# Animation function pulls a spectrum via get_spectrum() and plots it
def animate(test_count):
    # Set integration time
    int_time_ms = int_times[ test_count % len(int_times) ]
    Test_Set(0xb2, 0xbf, int_time_ms, 6)

    # read spectrum
    spectrum = get_spectrum()
    
    # graph spectrum
    ax1.grid(True, linestyle = "--")
    ax1.plot(pix, spectrum, linewidth=0.75, color="C%d" % (test_count % max(9, len(int_times))))
    ax1.set_ylim(auto = True)
    ax1.set_xlabel("pixel number")
    ax1.set_ylabel("counts")

# initialize test parameters
int_times = [ 25, 50, 100, 200, 400, 800 ] # millisec

# Prepare figure
fig = plt.figure()
ax1 = fig.add_subplot(1,1,1)
pix = np.linspace(1, PIXEL_COUNT, PIXEL_COUNT)

# Animated figure with refresh rate interval
ani = animation.FuncAnimation(fig, animate, interval=1000) # give user 1sec to read graph
plt.show()
