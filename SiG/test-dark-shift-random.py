import sys
import usb.core
import numpy as np
import random

from datetime import datetime
from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000

PIXELS = 1952

last_integ = 0
last_gain = 0
min_spectra = 100
spectra_sec = 60

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

def get_spectrum(integ_ms):
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

    timeout_ms = TIMEOUT_MS + (last_integ + integ_ms) * 2
    try:
        data = dev.read(0x82, PIXELS * 2, timeout=timeout_ms) 
    except usb.core.USBTimeoutError:
        print(f"caught USBTimeoutError even though timeout was {timeout_ms}ms")
        raise 

    spectrum = []
    for i in range(PIXELS):
        spectrum.append(data[i] | (data[i+1] << 8))
    return np.array(spectrum)

def set_integration_time(ms):
    send_cmd(0xb2, ms)

def set_gain(db):
    msb = int(round(db, 5)) & 0xff
    lsb = int((db- msb) * 256) & 0xff
    raw = (msb << 8) | lsb
    send_cmd(0xb7, raw)

def send_cmd(cmd, value=0, index=0, buf=BUF):
    # print(f"cmd 0x{cmd:02x}, value 0x{value:04x}, index 0x{index:04x}, buf {buf}")
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, BUF, TIMEOUT_MS)

last_integ = -1
last_gain = -1

while True:
    integ_ms = random.randint(10, 5000)
    gain_db = random.randint(0, 31)

    set_integration_time(integ_ms)
    set_gain(gain_db)

    # take ONE throwaway after setting acquisition parameters
    throwaway = get_spectrum(integ_ms)

    num_spectra = min(min_spectra, int(spectra_sec * 1000 / integ_ms))

    dark = get_spectrum(integ_ms)
    dark_med = np.median(dark)
    dark_time = datetime.now()
    print(f"# median dark at {integ_ms}ms, {gain_db}dB is {dark_med}")

    last_corr_med = -1
    for i in range(num_spectra):
        spectrum = get_spectrum(integ_ms)
        this_med = np.median(spectrum)
        corrected = spectrum - dark
        corr_med = np.median(corrected)
        now = datetime.now()

        elapsed_sec = (now - dark_time).total_seconds()

        if i > 0 and abs(corr_med) > 100 and abs(corr_med - last_corr_med) > (0.2 * abs(last_corr_med)):
            shift_warning = "SHIFT"
        else:                            
            shift_warning = ""

        print(f"{now}, elapsed_sec {elapsed_sec:5.1f}, last_integ {last_integ}, integ_ms {integ_ms}, last_gain {last_gain}, gain_db {gain_db}, spectrum {i+1:3d}/{num_spectra:3d}, median {this_med:8.1f}, corrected median {corr_med:-5.1f}, {shift_warning}")
        last_corr_med = corr_med

    last_integ = integ_ms
    last_gain = gain_db
