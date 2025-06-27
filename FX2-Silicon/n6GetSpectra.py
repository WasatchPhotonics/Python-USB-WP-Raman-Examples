#!/usr/bin/env python -u

import usb.core
import datetime
import sys
import time
from time import sleep
import matplotlib.pyplot as plt
import struct

# select product
dev=usb.core.find(idVendor=0x24aa, idProduct=0x4000)
if dev is None:
    print("Unable to find spectrometer")
    sys.exit(-1)

print (dev)
H2D=0x40
D2H=0xC0
BUFFER_SIZE=1
Z=[0] * BUFFER_SIZE
TIMEOUT=3000
MAX_SEC = 1000
INTEG_MS = 235

# select pixel count
PixelCount=2592*1944

#print("setting integration time to %d ms" % INTEG_MS)
#dev.ctrl_transfer(H2D, 0xb2, INTEG_MS, 0, Z, TIMEOUT) 

start_time = datetime.datetime.now()


def img_print_row(row_nr):
    print("row ", row_nr, ": ", 
          hex(spectrum[(2592*row_nr)]), 
          ", ",
          hex(spectrum[(2592*row_nr) + 1]),
          ", ",
          hex(spectrum[(2592*row_nr) + 2]),
          ", ",
          hex(spectrum[(2592*row_nr) + 3]),
          ", ",
          hex(spectrum[(2592*row_nr) + 4]),
          ", ",
          hex(spectrum[(2592*row_nr) + 5]),
          ", ",
          hex(spectrum[(2592*row_nr) + 6]),
          ", ",
          hex(spectrum[(2592*row_nr) + 7]))

firstSegRcvd = 0
count = 0
while (1):  # datetime.datetime.now() - start_time).total_seconds() < MAX_SEC:
    firstSegRcvd = 0
    print("sending acquire")
    # dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT)   # trigger an acquisition

    data = dev.ctrl_transfer(D2H, 0xb4, 0, 0, 1, TIMEOUT)
    print("reading data from EP 0x82 .....\n")

    ts0 = time.time()
    print("TS0: {:0.3f}".format(ts0))
    cumulative_data = []
    total_bytes_needed = PixelCount*2 
    tot_read = 0
    while len(cumulative_data) < total_bytes_needed:
        bytes_remaining = total_bytes_needed - len(cumulative_data)
        read_cnt = bytes_remaining
        if bytes_remaining > 1024:
           read_cnt = 1024

        # print(f"requesting {read_cnt} bytes with timeout {TIMEOUT}ms")
        latest_data = []
        latest_data = dev.read(0x82, read_cnt, timeout=TIMEOUT)
        if firstSegRcvd == 0:
            print("first seg sz rcvd", len(latest_data))
            ts1 = time.time()
            print("TS1: {:0.3f}".format(ts1))
            firstSegRcvd = 1
        # print("read %d bytes (%d requested)" % (len(latest_data), bytes_remaining))
        tot_read += len(latest_data)
        # print("tot rd", tot_read)
        # print(bytes_remaining)
        cumulative_data.extend(latest_data)

    print("Rcvd image ..")
    ts2 = time.time()
    #print("TS0:", ts0)
    #print("TS1:", ts1)
    # print("TS2:", ts2)
    # print("TS1-TS0 =", ts1 - ts0)
    # print("TS2-TS1 =", ts2 - ts1)
    print("TS2-TS0 = {:.3f} secs ".format(ts2 - ts0))
    data_rate = len(cumulative_data) * 8
    data_rate /= (ts2 - ts0)
    data_rate /= 1000000
    print("Throughput {:.3f} mbps".format(data_rate))

    # print("read cumulative %d bytes" % len(cumulative_data))

    # marshall bytes back into uint16 pixels
    spectrum = []
    for i in range(PixelCount):
        lsb = cumulative_data[i*2]
        msb = cumulative_data[i*2 + 1]
        intensity = lsb | (msb << 8)
        spectrum.append(intensity)

    # x_axis = []
    # for i in range(PixelCount):
    #   x_axis.append(i)

    print("Rcvd spectrum with pixel cnt", len(spectrum))
    img_print_row(0)
    img_print_row(1)
    img_print_row(2)
    img_print_row(1942)
    img_print_row(1943)
   

    pixCnt = len(spectrum)
    packed_bytes = b"".join([struct.pack('B', byte_val) for byte_val in cumulative_data])

    file_path = "raw10_11.raw"
    with open(file_path, "wb") as f:
      f.write(packed_bytes)
      print(f"Binary array saved to {file_path}")
      f.close()

    # if count == 1:
    #    plt.plot(x_axis, spectrum)
    #    plt.show()
    #    break
    # print("%4d %s: read spectrum of %d pixels: %s .. %s" % (count, datetime.datetime.now(), len(spectrum), spectrum[0:5], spectrum[-6:-1]))

    count += 1
    if count >= 1:
       break
