#!/usr/bin/python

import sys
import usb.core
import usb.util
import usb.control
import argparse
import inspect

import tkinter as tk

# def initUSB():
#     devList = usb.core.find(find_all=True)
#     for device in devList:
#       sys.stdout.write('Decimal VendorID=' + str(device.idVendor) + ' & ProductID=' + str(device.idProduct) + '\n')
#       sys.stdout.write('Hexadecimal VendorID=' + hex(device.idVendor) + ' & ProductID=' + hex(device.idProduct) + '\n\n')
#       if device.idVendor == 0x24aa and device.idProduct == 0x4000:
#         sys.stdout.write('Found Wasatch Spectrometer' + hex(device.idVendor) + ',  ' + hex(device.idProduct) + '\n')
#         return  device
#         break
#     
#     return None
# 
# def getFPGARevision(wdev):
#     if(wdev != None):
#         sys.stdout.write('Wasatch Device Captured ' + hex(wdev.idVendor) + ',  ' + hex(wdev.idProduct) + '\n')
#         wdev.set_configuration()
#         cfg = wdev.get_active_configuration()
#         interface = cfg[(0,0)]
#         rbuf = usb.util.create_buffer(7)
#         
#         bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
#         sys.stdout.write('bmReqType is ' + hex(bmReqType) + ' \n' + 'recv buf length is ' + str(len(rbuf)) + ' \n\n')
#         wdev.ctrl_transfer(bmReqType,0x81, 0x20, 0x00, rbuf)
#         sys.stdout.write('response from device for req = 0x81 is \n\n')
#         print('[{}]'.format(', '.join(hex(x) for x in rbuf)))
#         
# def setFPGARevision(wdev):
#         xmit_buf = usb.util.create_buffer(7)
#         xmit_buf = [0x51, 0x72, 0x73, 0x74, 0x75, 0x77, 0x78]
#         bmReqType = usb.util.build_request_type(usb.util.CTRL_OUT, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
#         sys.stdout.write('XMIT bmReqType is ' + hex(bmReqType) + ' \n' + 'recv buf length is ' + str(len(rbuf)) + ' \n\n')
#         wdev.ctrl_transfer(bmReqType,0x91, 0x00, 0, xmit_buf)
#         
#         bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
#         wdev.ctrl_transfer(bmReqType,0x81, 0x00, 0, rbuf)
#         
#         sys.stdout.write('response from device for req = 0x81 is \n\n')
#         print('[{}]'.format(', '.join(hex(x) for x in rbuf)))
#         
# def testCtrlTransfer(wdev, reg_address):
# 
#     if(wdev != None):
#         sys.stdout.write("Test " + hex(reg_address) + "\n")
#         rbuf = usb.util.create_buffer(64)
#         bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
#         wdev.ctrl_transfer(bmReqType,0x81, reg_address, 0x00, rbuf)
#         print(bytes(rbuf).decode('utf-8'))
#         
# def readRegister(wdev, reg_address):
# 
#     if(wdev != None):
#         sys.stdout.write("Read " + hex(reg_address) + "\n")
#         rbuf = usb.util.create_buffer(4)
#         bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
#         wdev.ctrl_transfer(bmReqType,0x81, reg_address, 0x00, rbuf)
#         sys.stdout.write("Read Reg  @"+hex(reg_address)+" = " )
#         print('[{}]'.format(', '.join(hex(x) for x in rbuf)))# find USB devices
# 
# def writeRegister(wdev, reg_address, reg_value):
# 
#     if(wdev != None):
#         sys.stdout.write("Write " + hex(reg_address) + " " + hex(reg_value) + "\n")
#         tbuf = usb.util.create_buffer(8)
#         bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
#         wdev.ctrl_transfer(bmReqType,0x91, reg_address, reg_value, tbuf)
#         sys.stdout.write("Write Reg  @"+hex(reg_address)+" = " + hex(reg_value) )
#         print('[{}]'.format(', '.join(hex(x) for x in tbuf)))# find USB devices
#         
# def ReadNewArchRegisters(wdev):
# 
#     for reg in registerList:
#         readRegister(wdev, reg)
#         
# def writeNewArchRegisters(wdev):
#     registerList = [0x0400, 0x0005, 0x0006, 0x0007, 0x0008, 0x0009, 0x000c,
#                     0x0010, 0x0020, 0x0024, 0x0025, 0x0026, 0x0040, 0x0041, 0x0042,
#                     0x0044, 0x0045, 0x0046, 0x0048, 0x004c, 0x0050, 0x0054, 0x0058,
#                     0x0059, 0x005A, 0x0080, 0x0081, 0x0084, 0x0088, 0x0089, 0x008A,
#                     0x008c, 0x008d, 0x008e, 0x0090, 0x0091, 0x0092, 0x0094, 0x0095, 
#                     0x00c0, 0x00c1, 0x00c2, 0x00c4, 0x00c8, 0x00c9, 0x00cc, 0x00d0,
#                     0x00d8, 0x00dc, 0x00e0, 0x00e4, 0x00e8]
#     
#     values       = [0x0102, 0x0304, 0x0506, 0x0708, 0x090A, 0x0B0C, 0x0D0E,
#                     0x0F10, 0x1112, 0x1314, 0x1516, 0x1718, 0x191A, 0x1B1C, 0x1D1E,
#                     0x1F20, 0x2122, 0x2324, 0x2526, 0x2728, 0x292A, 0x2B2C, 0x2D2E,
#                     0x2F30, 0x3132, 0x3334, 0x3536, 0x3738, 0x393A, 0x3B3C, 0x3D3E,
#                     0x3F40, 0x4142, 0x4344, 0x4546, 0x4748, 0x494A, 0x4B4C, 0x4D4E,
#                     0x4F50, 0x5152, 0x5354, 0x5556, 0x5758, 0x595A, 0x5B5C, 0x5D5E,
#                     0x5F70, 0x7172, 0x7374, 0x7576, 0x7778]
#                     
#     for reg, val in zip(registerList,values) :
#         writeRegister(wdev, reg, val)
#         
# def main():
#     # loop through devices, printing vendor and product ids in decimal and hex
#     wasatchDevice = None
#     regaddr = None
#     regValue = None
#     rdwrbit = None
#     #if(len(sys.argv) < 3):
#     #    sys.stdout.write("15 Usage: \npython " + sys.argv[0] + " r <reg_addr>\npython " + sys.argv[0] +" w <regaddr> <regval>\n")
#     #    return -1
#     
#     if(len(sys.argv) > 2):
#         rdwrbit = sys.argv[1] # read-write bit
#         regaddr = sys.argv[2]
#     
#     wasatchDevice = initUSB()
# 
#     match rdwrbit:
#         case 'r':
# 			readRegister(wasatchDevice, int(regaddr, 0))
#         case 'w':
#             if(len(sys.argv) < 4):
#                 sys.stdout.write("Usage: \npython " + sys.argv[0] + " w <regaddr> <regval>\n")
#                 return -1
#             else:
#                 regValue = sys.argv[3]
#                 writeRegister(wasatchDevice, int(regaddr, 0), int(regValue,0))
#         case 't':
# 			testCtrlTransfer(wasatchDevice, int(regaddr, 0))               
#         case _:
#             ReadNewArchRegisters(wasatchDevice)
#             writeNewArchRegisters(wasatchDevice)
#             ReadNewArchRegisters(wasatchDevice)
#             return -2

class RegisterUtil(tk.Tk):

    REGISTERS = [0x0000, 0x0400, 0x0005, 0x0006, 0x0007, 0x0008, 0x0009, 0x000c,
                 0x0010, 0x0020, 0x0024, 0x0025, 0x0026, 0x0040, 0x0041, 0x0042,
                 0x0044, 0x0045, 0x0046, 0x0048, 0x004c, 0x0050, 0x0054, 0x0058,
                 0x0059, 0x005A, 0x0080, 0x0081, 0x0084, 0x0088, 0x0089, 0x008A,
                 0x008c, 0x008d, 0x008e, 0x0090, 0x0091, 0x0092, 0x0094, 0x0095, 
                 0x00c0, 0x00c1, 0x00c2, 0x00c4, 0x00c8, 0x00c9, 0x00cc, 0x00d0,
                 0x00d8, 0x00dc, 0x00e0, 0x00e4, 0x00e8]

    def __init__(self):
        super().__init__()

        self.title("FPGA Register Utility")
        
        self.frame = tk.Frame(self)
        self.frame.grid(row=0, column=0, sticky="news")

        # what would these do?
        # self.grid_rowconfigure(0, weight=1)
        # self.grid_columnconfigure(1, weight=1)

        row = 0

        self.label_addr = tk.Label(self.frame, text="Address")
        self.label_addr.grid(row=row, column=1)

        self.label_value = tk.Label(self.frame, text="Value")
        self.label_value.grid(row=row, column=2)

        row += 1

        self.btn_write = tk.Button(self.frame, text="Write", command=self.write)
        self.btn_write.grid(row=row, column=0)

        self.text_write_addr = tk.Text(self.frame, height=1, width=6)
        self.text_write_addr.grid(row=row, column=1)

        self.text_write_value = tk.Text(self.frame, height=1, width=6)
        self.text_write_value.grid(row=row, column=2)

        row += 1

        self.btn_read = tk.Button(self.frame, text="Read", command=self.read)
        self.btn_read.grid(row=row, column=0)

        self.text_read_addr = tk.Text(self.frame, height=1, width=6)
        self.text_read_addr.grid(row=row, column=1)

        self.text_read_values = tk.Text(self.frame, height=10, width=6)
        self.text_read_values.grid(row=row, column=2)

        row += 1

        self.text_log = tk.Text(self.frame, height=5, width=50)
        self.text_log.grid(row=row, column=0, columnspan=3)

    def write(self):
        pass

    def read(self):
        pass

win = RegisterUtil()
win.mainloop()
