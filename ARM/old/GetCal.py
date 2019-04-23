#!/usr/bin/python

import sys
import usb.core
import struct

def main( argv ):
    dev=usb.core.find(idVendor=0x24aa, idProduct=0x0009)
    print(dev)
    H2D=0x40
    D2H=0xC0
    BUFFER_SIZE=32
    TIMEOUT=10
    
    CalibrationReadList = dev.ctrl_transfer(D2H, 0xa2, 0, 0, BUFFER_SIZE, TIMEOUT)

    print("Calibration Read: ")
    CalibrationReadStr1 = ''
    CalibrationReadStr2 = ''
    CalibrationReadStr3 = ''
    CalibrationReadStr4 = ''
    for chrs in range(BUFFER_SIZE/4):
        CalibrationReadStr1 += str(hex(CalibrationReadList[chrs     ])[2:].zfill(2))
        CalibrationReadStr2 += str(hex(CalibrationReadList[chrs +  8])[2:].zfill(2))
        CalibrationReadStr3 += str(hex(CalibrationReadList[chrs + 16])[2:].zfill(2))
        CalibrationReadStr4 += str(hex(CalibrationReadList[chrs + 24])[2:].zfill(2))

    print((struct.unpack('d', CalibrationReadStr1.decode('hex'))[0]))
    print((struct.unpack('d', CalibrationReadStr2.decode('hex'))[0]))
    print((struct.unpack('d', CalibrationReadStr3.decode('hex'))[0]))
    print((struct.unpack('d', CalibrationReadStr4.decode('hex'))[0]))
                
if __name__ == "__main__":
    main(sys.argv[1:])
