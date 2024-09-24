import sys
import usb.core
import numpy as np

from datetime import datetime
from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000

PIXELS = 1952

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

def get_spectrum():
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)
    data = dev.read(0x82, PIXELS * 2) 
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
    print(f"cmd 0x{cmd:02x}, value 0x{value:04x}, index 0x{index:04x}, buf {buf}")
    dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, BUF, TIMEOUT_MS)

all_integs      = list(range(  10,  100,   10))
all_integs.extend(list(range( 100, 1000,  100)))
all_integs.extend(list(range(1000, 5001, 1000)))

all_gains = list(range(0, 31))

last_integ = 0
last_gain = 0
min_spectra = 100
spectra_sec = 60

for integ_asc in [True, False]:

    for gain_asc in [True, False]:

        these_integs = all_integs if integ_asc else reverse(all_integs)
        these_gains = all_gains if gain_asc else reverse(all_gains)

        for integ_ms in these_integs:

            print(f"{'setting' if integ_ms == these_integs[0] else 'increasing' if integ_asc else 'decreasing'} integration time to {integ_ms} (resetting gain)")
            set_integration_time(integ_ms)

            # plan to collect dark spectra for at least spectra_sec (but not 
            # fewer than min_spectra)
            num_spectra = min(min_spectra, int(spectra_sec * 1000 / integ_ms))

            for gain_db in these_gains:

                print(f"{'setting' if gain_db == these_gains[0] else 'increasing' if gain_asc else 'decreasing'} gain to {gain_db}")
                set_gain(gain_db)

                dark = get_spectrum()
                dark_med = np.median(dark)
                print(f"median dark at {integ_ms}ms, {gain_db}dB is {dark_med}")

                for i in range(num_spectra):
                    spectrum = get_spectrum()
                    this_med = np.median(spectrum)
                    corrected = spectrum - dark
                    corr_med = np.median(corrected)
                    now = datetime.now()
                    
                    print(f"{now}, last_integ {last_integ}, integ_ms {integ_ms}, last_gain {last_gain}, gain_db {gain_db}, spectrum {i+1}/{num_spectra}, median {this_med}, corrected median {corr_med}")
                last_gain = gain_db
            last_integ = integ_ms
