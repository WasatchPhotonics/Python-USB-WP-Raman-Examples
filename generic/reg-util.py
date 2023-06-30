#!/usr/bin/python

import re
import sys
import usb.core
import usb.util
import usb.control
import inspect

import tkinter as tk
from tkinter import ttk

class RegisterUtil(tk.Tk):

    def __init__(self):
        super().__init__()

        if not self.init_usb():
            return

        self.init_table()
        self.init_gui()

    def init_usb(self):
        self.dev = None
        for dev in usb.core.find(find_all=True):
            if dev.idVendor == 0x24aa and dev.idProduct == 0x4000:
                print(f"found VID 0x{dev.idVendor:04x} PID 0x{dev.idProduct:04x}")
                self.dev = dev
                return True

    def make_addr_combobox(self, string_var, row, col):
        cb = ttk.Combobox(self, width=10, textvariable=string_var)
        cb.grid(row=row, column=col)
        cb['values'] = [self.reg[addr]["name"] for addr in self.reg.keys()]
        cb.current()
        return string_var

    def init_gui(self):
        self.title("FPGA Register Utility")

        row = 0
        tk.Label(text="Address").grid(row=row, column=1)
        tk.Label(text="Value").grid(row=row, column=2)

        row += 1
        tk.Button(text="Write", command=self.write).grid(row=row, column=0)
        self.write_addr = self.make_addr_combobox(tk.StringVar(), row, 1)
        self.write_value = tk.Text(height=1, width=6)
        self.write_value.grid(row=row, column=2)

        row += 1
        tk.Button(text="Read", command=self.read).grid(row=row, column=0)
        self.read_addr = self.make_addr_combobox(tk.StringVar(), row, 1)
        self.read_value = tk.Text(height=1, width=6)
        self.read_value.grid(row=row, column=2)

    def read(self):
        addr = self.read_addr.get()
        print(f"reading addr 0x{addr:04x}")

        buf = usb.util.create_buffer(4)
        bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR, usb.util.CTRL_RECIPIENT_DEVICE)
        self.dev.ctrl_transfer(bmReqType, 0x81, addr, 0x00, buf)
        
        value = 0
        for i in len(rbuf):
            value |= rbuf[i]
            value <<= 8

        print(f"read addr 0x{addr:04x} received 0x{value:04x}")

    def write(self):
        addr = self.write_addr.get()
        value = int(self.get_value(self.write_addr), 16)
        print(f"writing addr 0x{addr:04x} <- 0x{value:04x}")

        buf = usb.util.create_buffer(8)
        bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
        self.dev.ctrl_transfer(bmReqType, 0x91, addr, value, buf)

    def init_table(self):
        #   Name            Addr    Default Description
        #   --------------- ------- ------- ------------------------
        table = """
            REG_00          0x0000  0x0210  I2C Comm defaults
            REG_04          0x0004  0x6B0F  FPGA Revision[3] (RD Only)
            REG_05          0x0005  0xA35C  FPGA Revision[2] (RD Only)
            REG_06          0x0006  0x12D4  FPGA Revision[1] (RD Only)
            REG_07          0x0007  0x0863  FPGA Revision[0] (RD Only)
            REG_08          0x0008  0x0064  INTEGRATION_TIME[31:16]
            REG_09          0x0009  0x0900  INTEGRATION_TIME[15:0]
            REG_0C          0x000C  0x0C18  CONFIGURATION
            REG_10          0x0010  0x101C  CCD_OFFSET
            REG_14          0x0014  0x1420  CCD_GAIN
            REG_18          0x0018  0x1824  LASER_MOD_DURATION[47:32]
            REG_19          0x0019  0x1925  LASER_MOD_DURATION[31:16]
            REG_1A          0x001A  0x1A26  LASER_MOD_DURATION[15:0]
            REG_1C          0x001C  0x1C27  Spare
            REG_1D          0x001D  0x1D38  IMX Status
            REG_1E          0x001E  0x1E00  FPGA Status

            REG_40          0x0040  0x402A  LASER_MOD_PULSE_DELAY[47:32]
            REG_41          0x0041  0x412B  LASER_MOD_PULSE_DELAY[31:16]
            REG_42          0x0042  0x422C  LASER_MOD_PULSE_DELAY[15:0]
            REG_44          0x0043  0x442D  LASER_MOD_PERIOD[47:32]
            REG_45          0x0044  0x452E  LASER_MOD_PERIOD[31:16]
            REG_46          0x0045  0x462F  LASER_MOD_PERIOD[15:0]
            REG_48          0x0048  0x4830  FRAME_NUMBER
            REG_4C          0x004C  0x4C34  DATA_THRESHOLD
            REG_50          0x0050  0x5038  STATUS
            REG_54          0x0054  0x543C  LASER_TEMP
            REG_58          0x0058  0x5840  LASER_MOD_PULSE_WIDTH[47:32]
            REG_59          0x0059  0x5941  LASER_MOD_PULSE_WIDTH[31:16]
            REG_5A          0x005A  0x5A42  LASER_MOD_PULSE_WIDTH[15:0]
            REG_5C          0x005C  0x5C43  IMX385 Spectra
            REG_5D          0x005D  0x5D44  IMX385 Address (Register)
            REG_5E          0x005E  0x5E45  IMX385 Data (Register)

            REG_80          0x0080  0x8046  ACT_INTEGRATION_TIME[31:16]
            REG_81          0x0081  0x8147  ACT_INTEGRATION_TIME[15:0]
            REG_84          0x0084  0x8448  FRAME_COUNT
            REG_88          0x0088  0x884C  LASER_TRANS_3[47:32]
            REG_89          0x0089  0x894D  LASER_TRANS_3[31:16]
            REG_8A          0x008A  0x8A4E  LASER_TRANS_3[15:0]
            REG_8C          0x008C  0x8C50  LASER_TRANS_4[47:32]
            REG_8D          0x008D  0x8D51  LASER_TRANS_4[31:16]
            REG_8E          0x008E  0x8E52  LASER_TRANS_4[15:0]
            REG_90          0x0090  0x9054  LASER_TRANS_5[47:32]
            REG_91          0x0091  0x9155  LASER_TRANS_5[31:16]
            REG_92          0x0092  0x9256  LASER_TRANS_5[15:0]

            REG_94          0x0094  0x9494  Spare
            REG_95          0x0095  0x9595  Spare
            REG_96          0x0092  0x9696  Spare
            REG_97          0x0097  0x9797  Spare

            REG_C0          0x00C0  0xC058  LASER_TRANS_6[47:32]
            REG_C1          0x00C1  0xC159  LASER_TRANS_6[47:32]
            REG_C2          0x00C2  0xC25A  LASER_TRANS_6[47:32]
            REG_C4          0x00C4  0xC45C  LASER_SET_POINT
            REG_C8          0x00C8  0xC860  COMPILE_OPTIONS[31:16]
            REG_C9          0x00C9  0xC961  COMPILE_OPTIONS[15:0]
            REG_CC          0x00CC  0xCC64  LINE_LENGTH (Last Legacy)
            REG_D0          0x00D0  0xD068  Device ID (RD Only)
            REG_D4          0x00D4  0xD46C  Status (RD Only)
            REG_D8          0x00D8  0xD870  Trigger Mode
            REG_DC          0x00DC  0xDC74  Acquisition Mode
            REG_DD          0x00DD  0xDD78  Acquisition Delay
            REG_E0          0x00E0  0xE07C  FPGA Configuration
            REG_E4          0x00E4  0xE480  ADC Configuration
            REG_E8          0x00E8  0xE881  FIFO RD Pointer
            REG_E9          0x00E9  0xE982  FIFO WR Pointer
        """
        # parse the above table into a dict
        self.reg = {}
        for line in table.split("\n"):
            m = re.match("^\s*(\w+)\s+0x([0-9a-f]{4})\s+0x([0-9a-f]+)\s+(.*)", line, re.IGNORECASE)
            if m:
                name = m.group(1)
                addr = int(m.group(2), 16)
                default = int(m.group(3), 16)
                description = m.group(4)
                self.reg[addr] = { "name": name, "address": addr, "default": default, "description": description }
                # print(f"stored 0x{addr:04x} => {self.reg[addr]}")

util = RegisterUtil()
if not util.dev:
    print("No ARM-based Wasatch Photonics spectrometer found")
    sys.exit(1)

util.mainloop()
