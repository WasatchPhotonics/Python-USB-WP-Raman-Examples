#!/usr/bin/python
"""
authors: Bryan, Demetri, Mark, Murty, Samie
description: Read or Write specific register values to FPGA
"""

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
        REG_D5			0x00D5		0xD5D5		Spare
        REG_D6			0x00D6      0x0000		FIFO RD Pointer
        REG_D7			0x00D7		0x0000		FIFO WR Pointer
    """

    def __init__(self):
        super().__init__()

        if not self.init_usb():
            return

        self.init_reg_table()
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
        width = 250
        height = 450
        pad_y = 3
        pad_x = 3

        self.title("GLA Reg Util")
        self.geometry(f"{width}x{height}")

        row = 0
        tk.Label(text="IMX Functions").grid(row=row, column=0, padx=pad_x, pady=pad_y, columnspan=3)

        row += 1 # [ (INIT) | (READ) | (WRITE) ]
        self.btn_init_imx  = tk.Button(text="Initalize", command=self.btn_init_imx_clicked).grid(row=row, column=0, pady=pad_y, padx=pad_x)
        self.btn_init_imx  = tk.Button(text="Read IMX Reg", command=self.btn_read_imx_clicked).grid(row=row, column=1, pady=pad_y, padx=pad_x)
        self.btn_init_imx  = tk.Button(text="Write IMX Reg", command=self.btn_write_imx_clicked).grid(row=row, column=2, pady=pad_y, padx=pad_x)

        row += 1 # [ ]
        tk.Label(text="Bank:").grid(row=row, column=0, padx=pad_x, pady=pad_y)
        self.imx_bank = self.make_imx_bank_combobox(row, 1)

        self.textbox_write_imx_stringvar = StringVar()
        self.textbox_write_imx_stringvar.set('0000')
        self.textbox_write_imx_stringvar.trace("w", self.textbox_write_imx_textchanged)
        self.textbox_write_imx = tk.Entry(width=6, textvariable=self.textbox_write_imx_stringvar)

        # special case for backspace on 4 character hex display
        self.textbox_write_imx.bind("<BackSpace>", self.textbox_write_imx_backspace)

        self.textbox_write_imx.grid(row=row, column=2, pady=pad_y, padx=pad_x)
        
        row += 1 # [ ]
        tk.Label(text="Register:").grid(row=row, column=0, padx=pad_x, pady=pad_y)
        self.imx_addr = self.make_imx_addr_combobox(row, 1)

        self.read_imx_value = tk.StringVar(value="0xBEEF")
        tk.Label(height=1, width=6, textvariable=self.read_imx_value).grid(row=row, column=2, pady=pad_y, padx=pad_x)
        
        row += 1 # [ (___________________________) ]
        self.make_separator(row, 0, 3, pad_y)

        row += 1
        tk.Label(text="FPGA Status Registers").grid(row=row, column=0, columnspan=3)

        # REG_12 to REG_15, REG_47, REG_83, REG_C1, and REG_D0 to REG_D3
        # REFRESH ALL Button

        row += 1 # [ (___________________________) ]
        self.make_separator(row, 0, 3, pad_y)

        row += 1
        tk.Label(text="Individual Register Read / Write").grid(row=row, column=0, columnspan=3)

        row += 1 # [ (Write) | [name v] | [_____] ]
        self.btn_write = tk.Button(text="Write", command=self.btn_write_clicked).grid(row=row, column=0, pady=pad_y, padx=pad_x)
        self.write_addr = self.make_addr_combobox(row, 1)

        self.textbox_write_stringvar = StringVar()
        self.textbox_write_stringvar.set('0000')
        self.textbox_write_stringvar.trace("w", self.textbox_write_textchanged)
        self.textbox_write = tk.Entry(width=6, textvariable=self.textbox_write_stringvar)

        # special case for backspace on 4 character hex display
        self.textbox_write.bind("<BackSpace>", self.textbox_write_backspace)

        self.textbox_write.grid(row=row, column=2, pady=pad_y, padx=pad_x)

        row += 1 # [ (Read)  | [name v] | [_____] ]
        self.btn_read = tk.Button(text="Read", command=self.btn_read_clicked).grid(row=row, column=0, pady=pad_y, padx=pad_x)
        self.read_addr = self.make_addr_combobox(row, 1)
        self.read_value = tk.StringVar(value="0xBEEF")
        tk.Label(height=1, width=6, textvariable=self.read_value).grid(row=row, column=2, pady=pad_y, padx=pad_x)

        row += 1 # [ (__________READ_ALL_________) ]
        self.btn_read_all  = tk.Button(text="Read All to Terminal", width=20, command=self.btn_read_all_clicked).grid(row=row, column=0, pady=pad_y, padx=pad_x, columnspan=3)

        row += 1
        self.make_separator(row, 0, 3, pad_y)
        
        row += 1 # [ (_FPGA V: | [ver v] |         ]
        self.version_value = tk.StringVar(value="")
        self.get_FPGA_version()
        tk.Label(height=1, textvariable=self.version_value).grid(row=row, column=0, pady=pad_y, padx=pad_x, columnspan=3)

        row += 1 # [ (________GET FPGA VER_______) ]
        self.btn_init_imx  = tk.Button(text="Get FPGA Version", width=15, command=self.btn_get_fpga_ver_clicked).grid(row=row, column=0, pady=pad_y, padx=pad_x, columnspan=3)

        row += 1 # [ (___________________________) ]
        self.make_separator(row, 0, 3, pad_y)
        
        # keyboard shortcuts (untested)
        self.bind('<Control-R>', self.btn_read_clicked)
        self.bind('<Control-W>', self.btn_write_clicked)
        self.bind('<Control-V>', self.textbox_write.focus)
    
    ############################################################################
    # read/write methods
    ############################################################################
    
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

        return self.bswap_bytes(buf)
    
    def write(self, addr, val):
        """ writes values into fpga register """
        val = self.bswap_int(val)
        buf = usb.util.create_buffer(4)
        bmReqType = usb.util.build_request_type(usb.util.CTRL_IN, usb.util.CTRL_TYPE_VENDOR,usb.util.CTRL_RECIPIENT_DEVICE)
        self.dev.ctrl_transfer(bmReqType, 0x91, addr, val, buf)

    def read_imx(self, bank, addr):
        print()

    def write_imx(self, bank, addr, value):
        print()

    def bswap_bytes(self, buf):
        """ cuts to 16-bit and swaps BIG<->LITTLE from buffer byte array """
        # FPGA Sends and Receives in big endian
        # ARM translates the i2c address
        # ARM does not translate the data
        buf = buf[0:2]
        val = int.from_bytes(buf, "big")
        return val
    
    def bswap_int(self, val):
        """ cuts to 16-bit and swaps BIG<->LITTLE from int """
        # FPGA Sends and Receives in big endian
        # ARM translates the i2c address
        # ARM does not translate the data
        val = val.to_bytes(4, "little")
        val = val[0:2]
        val = int.from_bytes(val, "big")
        return val            
        
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
            self.write(addr, value)
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
    
    def textbox_write_imx_backspace(self, event):
        insert_index = self.textbox_write_imx.index("insert")
        if insert_index == 4:
            textcontent = self.textbox_write_imx_stringvar.get()
            textcontent = textcontent[:3].zfill(4)
            self.textbox_write_imx_stringvar.set(textcontent)
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

    def textbox_write_imx_textchanged(self, name, index, mode):
        textcontent = self.textbox_write_imx_stringvar.get()

        insert_index = self.textbox_write_imx.index("insert")
        
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

        self.textbox_write_imx_stringvar.set(filtered_textcontent)

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

    def btn_init_imx_clicked(self):
        print(" *** INIT IMX ***")
        print("Writing 0x30 to FPGA register REG_D2 to enable IMX.")
        self.write(0xD2, 0x30)
        print(f"  Read REG_D2: {self.read(0xD2):04x}")
        print("More initilization steps are required for full IMX operation and are not yet implemented.")
        print(" *** END INIT IMX ***")
    
    def btn_read_imx_clicked(self):
        """ IMX read is {0x8[BANK][REGISTER ADDRESS]} """
        print(" *** BEGIN IMX READ ***")
        bank = self.imx_bank.get()
        addr = self.imx_addr.get()
        print(f"Reading IMX bank {bank}, register {addr}...")
        print(f"Writing 0x8{bank}{addr} to FPGA register REG_56.")
        addr_val = int(f"8{bank}{addr}", 16)
        self.write(0x56, addr_val)
        print("Reading FPGA register REG_56 to confirm...")
        print(f"  Read REG_56: {self.read(0x56):04x}")
        print("Writing 0x0000 to FPGA register REG_57.")
        self.write(0x57, 0)
        print(f"Reading FPGA register REG_57 for IMX data...")
        value = self.read(0x57)
        print(f"  Read REG_57: {value:04x}")
        self.read_imx_value.set(f"0x{value:04x}")
        print(" *** END IMX READ ***")

    
    def btn_write_imx_clicked(self):
        """ IMX write is {0x0[BANK][REGISTER ADDRESS]} """
        print(" *** BEGIN IMX WRITE ***")
        bank = self.imx_bank.get()
        addr = self.imx_addr.get()
        try:
            s = self.textbox_write_imx.get().lower()
            if s.startswith("0x"):
                s = s[2:]
            value = int(s, 16)
        except:
            return
        print(f"Writing 0x{value:04x} into IMX bank {bank}, register {addr}...")
        print(f"Writing 0x0{bank}{addr} to FPGA register REG_56.")
        addr_val = int(f"0{bank}{addr}", 16)
        self.write(0x56, addr_val)
        print("Reading FPGA register REG_56 to confirm.")
        print(f"  Read REG_56: {self.read(0x56):04x}")
        print(f"Writing FPGA register REG_57 with data, 0x{value:04x}.")
        self.write(0x57, value)
        print("Reading FPGA register REG_57 to confirm.")
        print(f"  Read REG_57: {self.read(0x57):04x}")
        print("First byte is to confirm REG_57 was written, second byte is stale data.")
        print("Reading IMX register to confirm write operation.")
        print(f"Reading IMX bank {bank}, register {addr}...")
        print(f"Writing 0x8{bank}{addr} to FPGA register REG_56.")
        addr_val = int(f"8{bank}{addr}", 16)
        self.write(0x56, addr_val)
        print("Reading FPGA register REG_56 to confirm...")
        print(f"  Read REG_56: {self.read(0x56):04x}")
        print("Writing 0x0000 to FPGA register REG_57.")
        self.write(0x57, 0)
        print(f"Reading FPGA register REG_57 for IMX data...")
        value = self.read(0x57)
        print(f"  Read REG_57: {value:04x}")
        print(" *** END IMX WRITE ***")


    def btn_get_fpga_ver_clicked(self):
        self.get_FPGA_version()

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
    
    def make_imx_addr_combobox(self, row, col):
        """ 
        Utility method to generate a new Tk Combobox and pre-populate the 
        pull-down items with register address 00 through ff.

        Returns a Tk StringVar whose get() method can be used to read the current
        selection.
        """
        string_var = tk.StringVar()
        cb = ttk.Combobox(self, width=5, textvariable=string_var)
        cb.grid(row=row, column=col)
        addrs = []
        for i in range(256):
            addrs.append(f"{i:02x}")
        cb['values'] = addrs
        cb.current(0)
        return string_var
    
    def make_imx_bank_combobox(self, row, col):
        """ 
        Utility method to generate a new Tk Combobox and pre-populate the 
        pull-down items with imx banks 2, 3, 4, and 5.

        Returns a Tk StringVar whose get() method can be used to read the current
        selection.
        """
        string_var = tk.StringVar()
        cb = ttk.Combobox(self, width=5, textvariable=string_var)
        cb.grid(row=row, column=col)
        cb['values'] = [2, 3, 4, 5]
        cb.current(0)
        return string_var
    
    def make_separator(self, row, col, span, pad):
        return ttk.Separator(self, orient="horizontal").grid(row=row, column=col, columnspan=span, ipadx=100, pady=pad)

    def init_reg_table(self):
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

    def get_FPGA_version(self):
        """ read the FPGA registers for the version and set the version string """
        ver_string = ""
        for i in reversed(range(1, 5)):
            ver_string = ver_string + f"{self.read(i):02d}."
        
        print(f"Read FPGA Version: {ver_string[0:-1]}")
        self.version_value.set(f"FPGA Version: {ver_string[0:-1]}")

# main()
if __name__ == "__main__":
    util = RegisterUtil()
    if util.dev or offline_mode:
        util.mainloop()
