import sys
import usb.core
import numpy as np
import argparse
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
min_spectra = 200
spectra_sec = 120

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--random", action="store_true")
parser.add_argument("--start-line", type=int)
parser.add_argument("--stop-line", type=int)
args = parser.parse_args()

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
        spectrum.append(data[i*2] | (data[i*2+1] << 8))
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

def do_collection(integ_ms, gain_db):

    set_integration_time(integ_ms)
    set_gain(gain_db)

    # take ONE throwaway after changing gain
    throwaway = get_spectrum(integ_ms)

    dark = get_spectrum(integ_ms)
    dark_med = np.median(dark)
    dark_avg = np.mean(dark)
    dark_time = datetime.now()
    print(f"# dark at {integ_ms}ms {gain_db}dB: median {dark_med:.2f} avg {dark_avg:.2f}")

    # plan to collect dark spectra for at least spectra_sec (but not 
    # fewer than min_spectra)
    num_spectra = min(min_spectra, int(spectra_sec * 1000 / integ_ms))

    last_corr_med = 0
    for i in range(num_spectra):
        spectrum = get_spectrum(integ_ms)
        this_med = np.median(spectrum)
        this_avg = np.mean(spectrum)
        corrected = spectrum - dark
        corr_med = np.median(corrected)
        corr_avg = np.mean(corrected)
        now = datetime.now()

        edc_px = spectrum[0:4]
        edc_avg = round(np.mean(edc_px), 2)

        elapsed_sec = (now - dark_time).total_seconds()

        if i > 0 and abs(corr_med) > 100 and abs(corr_med - last_corr_med) > (0.2 * abs(last_corr_med)):
            shift_warning = "SHIFT"
        else:                            
            shift_warning = ""

        
        print(f"{now}, {elapsed_sec:5.1f}, " +
              f"{integ_ms}, {gain_db}, " +
              f"{i+1:3d}/{num_spectra:3d}, {this_med:8.1f}, {this_avg:8.1f}, {corr_med:-5.1f}, {corr_avg:-5.1f}, " +
              f"{edc_avg}, {edc_px[0]}, {edc_px[1]}, {edc_px[2]}, {edc_px[3]}, " +
              f"{shift_warning}")
        last_corr_med = corr_med

if args.start_line is not None and args.stop_line is not None:
    print(f"setting vertical ROI ({args.start_line}, {args.stop_line})")
    send_cmd(0xff, 0x21, args.start_line)
    send_cmd(0xff, 0x23, args.stop_line)

print("timestamp, elapsed_sec, integ_ms, gain_db, spectrum, median, mean, corrected median, corrected mean, edc_avg, edc_0, edc_1, edc_2, edc_3, warning")

if args.random:
    low = True
    while True:
        integ_ms = random.randint(10, 1000) if low else random.randint(1000, 5000)
        gain_db = random.randint(15, 31)
        do_collection(integ_ms, gain_db)

        last_integ = integ_ms
        low = not low
    
else:
    all_integs = [ 10, 25, 50, 100, 250, 500, 1000, 2000, 5000 ]
    all_gains = [ 16, 24, 30 ]

    for integ_asc in [True, False]:
        for gain_asc in [True, False]:

            print(f"# Changing to integ_asc {integ_asc}, gain_asc {gain_asc}")
            these_integs = all_integs if integ_asc else list(reversed(all_integs))
            these_gains  = all_gains  if gain_asc  else list(reversed(all_gains))

            for integ_ms in these_integs:

                print(f"# {'setting' if integ_ms == these_integs[0] else 'increasing' if integ_asc else 'decreasing'} integration time to {integ_ms} (resetting gain)")
                for gain_db in these_gains:

                    print(f"# {'setting' if gain_db == these_gains[0] else 'increasing' if gain_asc else 'decreasing'} gain to {gain_db}")
                    do_collection(integ_ms, gain_db)

                last_integ = integ_ms
