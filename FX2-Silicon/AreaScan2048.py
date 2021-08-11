import usb.core
import datetime
import sys

from time import sleep

dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
if dev is None:
    print("No spectrometer found")
    sys.exit(-1)

H2D         = 0x40
D2H         = 0xC0
TIMEOUT     = 1000
DELAY_MS    = 5     # value of 1 causes to eventually fall over
OFFSET_MS   = 5     # if that unit doesn't freak you out, you're not paying attention
Z = [0] * 8

# select pixel count
pixels = 2048
integ_time_ms = 1000

print("setting integration time %d ms" % integ_time_ms)
dev.ctrl_transfer(H2D, 0xb2, integ_time_ms, 0, Z, TIMEOUT)   

print("setting offset %d ms" % OFFSET_MS)
dev.ctrl_transfer(H2D, 0xb6, OFFSET_MS, 0, Z, TIMEOUT)   

print("AREA_SCAN_ENABLE = 1")
dev.ctrl_transfer(H2D, 0xeb, 1, 0, Z, TIMEOUT)   

for loop in range(3):
    print("ACQUIRE %d" % loop)
    time_start = datetime.datetime.now()
    dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   
    for row in range(70):
        spectrum = []
        for ep in (0x82, 0x86):
            data = dev.read(ep, pixels, TIMEOUT + integ_time_ms * 2)
            for i in range(len(data) // 2):
                lsb = data[i*2]
                msb = data[i*2 + 1]
                intensity = (msb << 8) | lsb
                spectrum.append(intensity)
            sleep(DELAY_MS * 1e-3)

        len_ = len(spectrum)
        print("Row %03d: %d pixels %s .. %s" % (spectrum[0], len_, spectrum[0:5], spectrum[len_-6:len_-1]))
    print("frame received in %.2f sec" % (datetime.datetime.now() - time_start).total_seconds())
print("AREA_SCAN_ENABLE = 0")
dev.ctrl_transfer(H2D, 0xeb, 0, 0, Z, TIMEOUT)   
