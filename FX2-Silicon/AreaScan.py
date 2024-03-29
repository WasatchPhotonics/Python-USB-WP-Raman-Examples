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
DELAY_MS    = 0 # value of 1 causes to eventually fall over
OFFSET_MS   = 0  # if that unit doesn't freak you out, you're not paying attention
Z = [0] * 8

# select pixel count
pixels = 1024
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
        data = dev.read(0x82, pixels * 2, TIMEOUT + integ_time_ms * 2)
        sleep(DELAY_MS * 0.001)

        for i in range(pixels):
            lsb = data[i*2]
            msb = data[i*2 + 1]
            intensity = (msb << 8) | lsb
            spectrum.append(intensity)

        print("Row %03d: %s .. %s" % (spectrum[0], spectrum[0:5], spectrum[pixels-6:pixels-1]))

    print("frame received in %.2f sec" % (datetime.datetime.now() - time_start).total_seconds())

print("AREA_SCAN_ENABLE = 0")
dev.ctrl_transfer(H2D, 0xeb, 0, 0, Z, TIMEOUT)   
