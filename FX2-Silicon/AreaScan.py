import usb.core
import datetime
import time
from time import sleep

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x1000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x2000)
#dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=8
Z='\x00'*BUFFER_SIZE
TIMEOUT=1000

# select pixel count
#PixelCount=512
PixelCount=1024				
#PixelCount=2048


print ("Set integration time")
dev.ctrl_transfer(H2D, 0xb2, 100, 0, Z, TIMEOUT)   # set integration time to 100ms

print ("Start Area Scan")
dev.ctrl_transfer(H2D, 0xeb, 1,0,Z,TIMEOUT)   # trigger an acquisition

for row in range(70):
    # print ("Start Data Acquisition")
    dev.ctrl_transfer(H2D, 0xad, 0,0,Z,TIMEOUT)   # trigger an acquisition
    Data = dev.read(0x82,PixelCount*2)
    spectrum = []
    for pixel in range(PixelCount):
        lsb = Data[pixel*2]
        msb = Data[pixel*2 + 1]
        intensity = (msb << 8) | lsb
        spectrum.append(intensity)
    print("Row %03d: %s .. %s" % (spectrum[0], spectrum[0:5], spectrum[PixelCount-6:PixelCount-1]))