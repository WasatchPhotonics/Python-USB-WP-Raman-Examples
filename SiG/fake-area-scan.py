import sys
import usb.core

from time import sleep
from copy import copy
import png

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000

PIXELS = 1952

FIRST_LINE = 100 
LAST_LINE  = 900
INCR       = 5

THROWAWAYS = 1
dev = None

def set_startline(line):
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0x21, line, BUF, TIMEOUT_MS)

def set_stopline(line):
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xff, 0x23, line, BUF, TIMEOUT_MS)

def get_spectrum():
    print("sending ACQUIRE")
    dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, BUF, TIMEOUT_MS)

    print(f"reading {PIXELS} from bulk endpoint")
    data = dev.read(0x82, PIXELS * 2) 

    spectrum = []
    for i in range(PIXELS):
        spectrum.append(data[i*2] | (data[i*2+1] << 8))

    # stomp endpoints
    for i in range(3):
        spectrum[i] = spectrum[3]
    spectrum[1951] = spectrum[1950]

    sleep(0.2)

    return spectrum

def get_clean_spectrum():
    for i in range(THROWAWAYS):
        get_spectrum()
    return get_spectrum()

# normalize to 256 shades of grey
def normalize(spectra):
    hi = max([max(spectrum) for spectrum in spectra])
    for y in range(len(spectra)):
        for x in range(len(spectra[y])):
            orig = spectra[y][x]
            spectra[y][x] = min(255, int((512.0 * orig / hi)))

def make_png(filename, spectra):
    with open(filename, 'wb') as f:
        w = png.Writer(width=len(spectra[0]), height=len(spectra))
        w.write(f, spectra)

################################################################################
# main()
################################################################################

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

spectra = []
for start_line in range(FIRST_LINE, LAST_LINE + 1, INCR):
    stop_line = start_line + INCR 

    print(f"Processing vertical ROI ({start_line}, {stop_line})")

    set_startline(start_line)
    set_stopline(stop_line)

    spectrum = get_clean_spectrum()

    # fill-out full 1080p image
    for _ in range(INCR):
        spectra.append(copy(spectrum))

normalize(spectra)
make_png("area_scan.png", spectra)
