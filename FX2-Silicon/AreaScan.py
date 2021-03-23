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

integ_time_ms = 5000

print ("PixelCount: ", PixelCount)
print ("Set integration time")
dev.ctrl_transfer(H2D, 0xb2, integ_time_ms, 0, Z, TIMEOUT)   # set integration time

#print ("Start Area Scan")
dev.ctrl_transfer(H2D, 0xeb, 1,0,Z,TIMEOUT)   # trigger an acquisition

# print ("Start Data Acquisition")

dev.ctrl_transfer(H2D, 0xad, 0,0,Z,TIMEOUT)   # trigger an acquisition

bytesRead = 0
bytesToRead = 2048
spectrum = []
fullSpectrum = []

for row in range(70):
    print("ROW: " , row)

    #dev.ctrl_transfer(H2D, 0xad, 0,0,Z,TIMEOUT)   # trigger an acquisition
    #sleep(0.00001)

    while bytesRead < bytesToRead:
    
        nextSpectrum = []
        Data = dev.read(0x82,PixelCount*2, TIMEOUT + integ_time_ms * 2)
        print("Data (%d bytes): " % len(Data), Data)
        #print("Data (%d bytes): " % len(Data))

        for pixel in range(int(len(Data)/2)):
            lsb = Data[pixel*2]
            msb = Data[pixel*2 + 1]
            intensity = (msb << 8) | lsb
            
            fullSpectrum.append(intensity)

            if len(spectrum) < PixelCount:
                spectrum.append(intensity)
            else:
                nextSpectrum.append(intensity)
                
            
        bytesRead += len(Data)
        
    print("Row %03d: %s .. %s" % (spectrum[0], spectrum[0:5], spectrum[PixelCount-6:PixelCount-1]))
    spectrum = nextSpectrum
    bytesRead -= bytesToRead
    print("Carrying over from previous read: %d bytes (%d pixels)" % (bytesRead, len(spectrum)))
#print("Full spectrum: %s " % fullSpectrum)