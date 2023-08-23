#!/usr/bin/python

import sys
import usb.core
import usb.util

import tkinter as tk
from tkinter import ttk
from tkinter import StringVar

# The UI is being developed by Samie who does not have a device that is 
# compatible with these instructions. She will run this with 
#offline_mode = True
# The full program will be executed by Demetrios or Murty who will use
#offline_mode = False
# This should only be pushed to git with offline_mode = False
offline_mode = False

# offline memory is used in offline mode so I can test
# writing to a register, followed by reading it's value back
offline_mem = {}

class RegisterUtil(tk.Tk):

    """ Copied from ENG-xxx FPGA Internal Register Bank Definitions """
    # Copied in by BAUZ 08-23-2023
    #   Name            Addr    Default Description
    #   --------------- ------- ------- ------------------------
    REGISTERS = """
        REG_00			0x0000		0x0210      I2C Comm defaults, (RD Only)
        REG_01			0x0001		0x0005      FPGA Revision[15:0], (RD Only)
        REG_02			0x0002		0x0000      FPGA Revision[31:16], (RD Only)
        REG_03			0x0003      0x0000      FPGA Revision[47:32], (RD Only)
        REG_04			0x0004		0x0000      FPGA Revision[63:48], (RD Only)
        REG_05			0x0005		0x0064      INTEGRATION_TIME[15:0]
        REG_06			0x0006		0x0600      INTEGRATION_TIME[31:16]
        REG_07			0x0007		0x0707      Spare
        REG_10			0x0010		0x1000      CCD_OFFSET
        REG_11			0x0011		0x1100      CCD_GAIN
        REG_12			0x0012		0x0001      COI Start  (Column of Interest)
        REG_13			0x0013		0x01E8      COI End 
        REG_14			0x0014		0x0009      ROI Start (Row of Interest)
        REG_15			0x0015		0x045A      ROI End 
        REG_16			0x0016		0x1616      Spare
        REG_17			0x0017		0x1717      Spare
        REG_40			0x0040		0x402A		LASER_MOD_PULSE_DELAY[15:0]
        REG_41			0x0041		0x412B		LASER_MOD_PULSE_DELAY[31:16]
        REG_42			0x0042   	0x422C		LASER_MOD_PULSE_DELAY[47:32]
        REG_43			0x0043		0x432D		LASER_MOD_PERIOD[15:0]
        REG_44			0x0044		0x442E		LASER_MOD_PERIOD[31:16]
        REG_45			0x0045		0x452F		LASER_MOD_PERIOD[47:32]
        REG_46			0x0046		0x4630		Laser Temp 
        REG_47			0x0047		0x4700		Laser Control 
        REG_50			0x0050		0x5000		LASER_SET_POINT
        REG_51			0x0051		0x5101		LASER_MOD_PULSE_WIDTH(15 :  0)
        REG_52			0x0052		0x5204		LASER_MOD_PULSE_WIDTH(31 :  16)
        REG_53			0x0053		0x5308		LASER_MOD_PULSE_WIDTH(47 :  32)
        REG_54			0x0054		0x5400		IMX_Spectra[15:0]
        REG_55			0x0055		0x5500		x"55", IMX385_Spectra[23:16]
        REG_56			0x0056		0x0000		IMX Address (Register)
        REG_57			0x0057		0xFFFF		IMX Data (Register)
        REG_80			0x0080		0x8000		DATA_THRESHOLD
        REG_81			0x0081		0x8101		FRAME_NUMBER
        REG_82			0x0082   	0x8201		FRAME_COUNT  
        REG_83			0x0083		0x0000		Acquisition Mode
        REG_84			0x0084		0x0000		Acquisition Delay
        REG_85			0x0085		0x0001		Trigger Control[15:0]
        REG_86			0x0086		0x8686		Spare
        REG_87			0x0087		0x8787		Spare
        REG_90			0x0090		0x0000		Light Control
        REG_91			0x0091		0x0000		Single Strobe Delay
        REG_92			0x0092		0x0000		Single Strobe Width
        REG_93			0x0093		0x0000		Continuous Strobe Period
        REG_94			0x0094		0x9494		Spare
        REG_95			0x0095		0x9595		Spare 
        REG_96			0x0096 	    0x9696		Spare
        REG_97			0x0097		0x9797		Spare
        REG_C0			0x00C0		0xC000		GPIO
        REG_C1			0x00C1		0x0000		Interrupt Vector
        REG_C2			0x00C2      0xC25A		ADC Configuration
        REG_C3			0x00C4		0xC3C3		Spare
        REG_C4			0x00C4		0xC4C4		Spare
        REG_C5			0x00C5		0xC561		Read Out Time
        REG_C6			0x00C6		0x0799		LINE_LENGTH (Last Legacy)
        REG_C7			0x00C7		0x0101		Device ID (RD Only)
        REG_D0			0x00D0		0x0000		FPGA Control/Config
        REG_D1			0x00D1		0x0000		FPGA Status (RD Only)
        REG_D2			0x00D2		0x0000		IMX Control/Status
        REG_D3			0x00D3		0x0000		BLE Control/Status
        REG_D4			0x00D4		0xD4D4		Spare
        REG_D5			0x00D5		0xD4D4		Spare
        REG_D6			0x00D6      0x0000		FIFO RD Pointer
        REG_D7			0x00D7		0x0000		FIFO WR Pointer
    """

    def __init__(self):
        super().__init__()

        if not self.init_usb():
            return

        self.init_table()
        self.init_gui()

    def init_usb(self):
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)
        if offline_mode:
            print("Starting in Offline Mode: ignoring connected spectrometers and showing messages in stdout.")
            return True
        elif self.dev:
            print(f"found VID 0x{self.dev.idVendor:04x} PID 0x{self.dev.idProduct:04x}")
            self.dev.set_configuration()
            usb.util.claim_interface(self.dev, 0)
            return True
        else:
            print("No ARM-based Wasatch Photonics spectrometer found")
            return False

    def init_gui(self):
        self.title("FPGA Register Utility")
        self.geometry("400x200")

        row = 0  # [         | Address  |  Value  ]
        tk.Label(text="Address").grid(row=row, column=1)
        tk.Label(text="Value").grid(row=row, column=2)

        row += 1 # [ (Write) | [name v] | [_____] ]
        self.btn_write = tk.Button(text="Write", command=self.btn_write_clicked).grid(row=row, column=0)
        self.write_addr = self.make_addr_combobox(row, 1)

        self.textbox_write_stringvar = StringVar()
        self.textbox_write_stringvar.set('0000')
        self.textbox_write_stringvar.trace("w", self.textbox_write_textchanged)
        self.textbox_write = tk.Entry(width=6, textvariable=self.textbox_write_stringvar)

        # special case for backspace on 4 character hex display
        self.textbox_write.bind("<BackSpace>", self.textbox_write_backspace)

        self.textbox_write.grid(row=row, column=2)

        row += 1 # [ (Read)  | [name v] | [_____] ]
        self.btn_read = tk.Button(text="Read", command=self.btn_read_clicked).grid(row=row, column=0)
        self.read_addr = self.make_addr_combobox(row, 1)
        self.read_value = tk.StringVar(value="0xBEEF")
        tk.Label(height=1, width=6, textvariable=self.read_value).grid(row=row, column=2)

        row += 1 # [ (__________READ_ALL________) ]
        self.btn_read_all  = tk.Button(text="Read All", width=30, command=self.btn_read_all_clicked).grid(row=row, column=0, columnspan=3)

        # keyboard shortcuts (untested)
        self.bind('<Control-R>', self.btn_read_clicked)
        self.bind('<Control-W>', self.btn_write_clicked)

        self.bind('<Control-V>', self.textbox_write.focus)

    def read(self, addr):
        """ reads register and returns value as int """
        buf = usb.util.create_buffer(4)
        if not offline_mode:
            bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR, usb.util.CTRL_RECIPIENT_DEVICE)
            self.dev.ctrl_transfer(bmReqType, 0x81, addr, 0x00, buf)
        else:
            # respond to reads with offline memory (default to 'beef') in offline mode
            buf[0] = offline_mem.get(2*addr, 0xbe)
            buf[1] = offline_mem.get(2*addr+1, 0xef)
        
        value = 0
        if True:
            # currently assuming register values are returned little-endian (network order)
            for i in range(2):
                value <<= 8
                value |= buf[i]
        else:
            # ...if it turns out to be big-endian, easy fix :-)
            for i in range(1, -1, -1):
                value <<= 8
                value |= buf[i]

        return value

    ############################################################################
    # event callbacks
    ############################################################################

    def btn_write_clicked(self):
        """ user clicked the "write" button """
        name = self.write_addr.get().strip()
        if name not in self.reg:
            return

        addr = self.reg[name]["addr"]
        desc = self.reg[name]["desc"]
        try:
            s = self.textbox_write.get().lower()
            if s.startswith("0x"):
                s = s[2:]
            value = int(s, 16)
        except:
            return

        print(f"writing {name} 0x{addr:04x} <- 0x{value:04x} ({desc})")

        if not offline_mode:
            buf = usb.util.create_buffer(8)
            bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
            self.dev.ctrl_transfer(bmReqType, 0x91, addr, value, buf)
        else:
            # in offline mode, fake a memset in internal memory
            offline_mem[2*addr] = int(s[0:2], 16)
            offline_mem[2*addr+1] = int(s[2:4], 16)

    def textbox_write_backspace(self, event):
        insert_index = self.textbox_write.index("insert")
        if insert_index == 4:
            textcontent = self.textbox_write_stringvar.get()
            textcontent = textcontent[:3].zfill(4)
            self.textbox_write_stringvar.set(textcontent)
            # when deleting last character, keep cursor at end
            return "break"

    def textbox_write_textchanged(self, name, index, mode):
        textcontent = self.textbox_write_stringvar.get()

        insert_index = self.textbox_write.index("insert")
        
        # emulate 'replace mode'
        textcontent = textcontent[:insert_index] + textcontent[insert_index+1:]

        # we make sure that there's only 0-f characters
        # and that there's always 4.
        filtered_textcontent = ""
        for c in textcontent:
            if c in "0123456789abcdefABCDEF":
                filtered_textcontent += c
        filtered_textcontent = filtered_textcontent[:4]
        filtered_textcontent = filtered_textcontent.zfill(4)

        self.textbox_write_stringvar.set(filtered_textcontent)

    def btn_read_clicked(self):
        """ user clicked the "read" button """
        """ reads register and returns value as int """
        name = self.read_addr.get()
        if name not in self.reg:
            return

        addr = self.reg[name]["addr"]
        desc = self.reg[name]["desc"]
        print(f"reading {name} 0x{addr:04x} ({desc})")
        value = self.read(addr)

        self.read_value.set(f"0x{value:04x}")
        print(f"read {name} 0x{addr:04x} received 0x{value:04x}")

    def btn_read_all_clicked(self):
        print("Name       Addr     Value    Default   Description")
        print("------     ------   ------   -------   ------------------------")

        for name in sorted(self.reg):
            addr = self.reg[name]["addr"]
            desc = self.reg[name]["desc"]
            default = self.reg[name]["default"]
            value = self.read(addr)
            print(f"{name:8s}   0x{addr:04x}   0x{value:04x}   0x{default:04x}    {desc}")

    ############################################################################
    # methods
    ############################################################################

    def make_addr_combobox(self, row, col):
        """ 
        Utility method to generate a new Tk Combobox and pre-populate the 
        pull-down items with the NAME of each register.

        Returns a Tk StringVar whose get() method can be used to read the current
        selection.
        """
        string_var = tk.StringVar()
        cb = ttk.Combobox(self, width=10, textvariable=string_var)
        cb.grid(row=row, column=col)
        cb['values'] = sorted(self.reg.keys())
        cb.current(0)
        return string_var

    def init_table(self):
        """ parse the register table into a dict """
        self.reg = {}
        for line in self.REGISTERS.split("\n"):
            tok = line.strip().split()
            if len(tok) > 3:
                name = tok[0]
                addr = int(tok[1][2:], 16)
                default = int(tok[2][2:], 16)
                desc = " ".join(tok[3:])
                self.reg[name] = { "addr": addr, "default": default, "desc": desc }

# main()
if __name__ == "__main__":
    util = RegisterUtil()
    if util.dev or offline_mode:
        util.mainloop()
