#!/usr/bin/python

import sys
import usb.core
import struct

def main( argv ):
	dev=usb.core.find(idVendor=0x24aa, idProduct=0x0009)
	print dev
	H2D=0x40
	D2H=0xC0
	BUFFER_SIZE=32
	TIMEOUT=10
	
	print "New Calibration Write:"
	CalFloat1 = float(argv[0])
	CalFloat2 = float(argv[1])
	CalFloat3 = float(argv[2])
	CalFloat4 = float(argv[3])
	AsciiNum = []

	i = 0
	for c in struct.pack('4d', CalFloat1, CalFloat2, CalFloat3, CalFloat4):
		print hex(ord(c))[2:].zfill(2),
		AsciiNum.append(ord(c))
		if not ((i+1) % 16):
			print(' ')	

		i += 1
	print

	dev.ctrl_transfer(H2D, 0xf5, 0, 0, AsciiNum, TIMEOUT)
	print "New Calibration Read: "
	CalibrationReadList = dev.ctrl_transfer(D2H, 0xa2, 0, 0, BUFFER_SIZE, TIMEOUT)
	for chrs in range(BUFFER_SIZE):
		print hex(CalibrationReadList[chrs])[2:].zfill(2),
		if not ((chrs+1) % 16):
			print(' ')	

	print(' ')	
	CalibrationReadStr1 = ''
	CalibrationReadStr2 = ''
	CalibrationReadStr3 = ''
	CalibrationReadStr4 = ''
	for chrs in range(BUFFER_SIZE/4):
		CalibrationReadStr1 += str(hex(CalibrationReadList[chrs     ])[2:].zfill(2))
		CalibrationReadStr2 += str(hex(CalibrationReadList[chrs +  8])[2:].zfill(2))
		CalibrationReadStr3 += str(hex(CalibrationReadList[chrs + 16])[2:].zfill(2))
		CalibrationReadStr4 += str(hex(CalibrationReadList[chrs + 24])[2:].zfill(2))

	print struct.unpack('d', CalibrationReadStr1.decode('hex'))[0]
	print struct.unpack('d', CalibrationReadStr2.decode('hex'))[0]
	print struct.unpack('d', CalibrationReadStr3.decode('hex'))[0]
	print struct.unpack('d', CalibrationReadStr4.decode('hex'))[0]
						
if __name__ == "__main__":
    main(sys.argv[1:])
