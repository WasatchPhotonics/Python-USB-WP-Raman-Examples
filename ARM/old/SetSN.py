#!/usr/bin/python

import sys
import usb.core
from time import sleep

# see "1-Wire CRC", https://www.maximintegrated.com/en/app-notes/index.mvp/id/27
crctab = [ # 16 x 16
     0,   94,  188, 226, 97,  63,  221, 131, 194, 156, 126, 32,  163, 253, 31,  65,
     157, 195, 33,  127, 252, 162, 64,  30,  95,  1,   227, 189, 62,  96,  130, 220,
     35,  125, 159, 193, 66,  28,  254, 160, 225, 191, 93,  3,   128, 222, 60,  98,
     190, 224, 2,   92,  223, 129, 99,  61,  124, 34,  192, 158, 29,  67,  161, 255,
     70,  24,  250, 164, 39,  121, 155, 197, 132, 218, 56,  102, 229, 187, 89,  7,
     219, 133, 103, 57,  186, 228, 6,   88,  25,  71,  165, 251, 120, 38,  196, 154,
     101, 59,  217, 135, 4,   90,  184, 230, 167, 249, 27,  69,  198, 152, 122, 36,
     248, 166, 68,  26,  153, 199, 37,  123, 58,  100, 134, 216, 91,  5,   231, 185,
     140, 210, 48,  110, 237, 179, 81,  15,  78,  16,  242, 172, 47,  113, 147, 205,
     17,  79,  173, 243, 112, 46,  204, 146, 211, 141, 111, 49,  178, 236, 14,  80,
     175, 241, 19,  77,  206, 144, 114, 44,  109, 51,  209, 143, 12,  82,  176, 238,
     50,  108, 142, 208, 83,  13,  239, 177, 240, 174, 76,  18,  145, 207, 45,  115,
     202, 148, 118, 40,  171, 245, 23,  73,  8,   86,  180, 234, 105, 55,  213, 139,
     87,  9,   235, 181, 54,  104, 138, 212, 149, 203, 41,  119, 244, 170, 72,  22,
     233, 183, 85,  11,  136, 214, 52,  106, 43,  117, 151, 201, 74,  20,  246, 168,
     116, 42,  200, 150, 21,  75,  169, 247, 182, 232, 10,  84,  215, 137, 107, 53]

def crc(CharList):
    val = 0
    for x in CharList:
        val = crctab[val ^ x]
    return val

def main( argv ):
    print("Usage: SetSN.py 'max15char string'")
    print("New Serial Number Write:", end=' ')
    RawString = argv[0]
    SNString = RawString[:BUFFER_SIZE-1]
    
    StringLength = SNString.__len__()
    for i in range(BUFFER_SIZE-1 - StringLength):
        SNString += ' '
    AsciiNum = []
    for x in SNString:
        NewChar = ord(x)
        AsciiNum.append(ord(x))
        if NewChar <= 0x20 or NewChar >= 0x7F:
            print(hex(NewChar), end=' ')
        else:
            print(chr(NewChar), end=' ')
        
    CRCOutput = crc(AsciiNum)
    AsciiNum.append(CRCOutput)
    print('CRC: ' + hex(CRCOutput))

    dev=usb.core.find(idVendor=0x24aa, idProduct=0x0009)
    print(dev)
    H2D=0x40
    D2H=0xC0
    BUFFER_SIZE=16
    TIMEOUT=10
    
    dev.ctrl_transfer(H2D, 0xf6, 0, 0, AsciiNum, TIMEOUT)
    sleep(0.02) # Time in second
    
    print("New Serial Number Read: ", end=' ')
    OldSerialNumList = dev.ctrl_transfer(D2H, 0xa3, 0, 0, BUFFER_SIZE, TIMEOUT)
    for chrs in range(BUFFER_SIZE):
        if chrs == BUFFER_SIZE-1 :
            print('CRC:', end=' ')
            print(hex(OldSerialNumList[chrs]), end=' ')
        elif OldSerialNumList[chrs] <= 0x20 or OldSerialNumList[chrs] >= 0x7F:
            print(hex(OldSerialNumList[chrs]), end=' ')
        else:
            print(chr(OldSerialNumList[chrs]), end=' ')
    print()
    
if __name__ == "__main__":
    main(sys.argv[1:])

