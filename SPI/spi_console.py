"""
Troubleshooting:
    - If it seems to "freeze" at startup, make sure you're setting your READY / 
      TRIGGER pins correctly.

Observations:
    - When I'm away from testing for awhile (10min+?) I often have to power-cycle
      the spectrometer when I resume.  This could be an problem with the FT232H 
      dongle or my laptop of course. 
"""

import tkinter as tk
import tkinter.ttk as ttk

import threading
import argparse
import logging
import time
import sys
import os

os.environ["BLINKA_FT232H"] = "1"
try:
    import board
except RuntimeError as ex:
    print("No FT232H connected.\n")
    raise(ex)
except ValueError as ex:
    print("If you are receiving 'no backend available' errors, try the following:\n")
    print("MacOS:  $ export DYLD_LIBRARY_PATH=/usr/local/lib")
    print("Linux:  $ export LD_LIBRARY_PATH=/usr/local/lib\n")
    raise(ex)
except FtdiError as ex:
    print("No FT232H connected.\n")
    raise(ex)
import digitalio
import busio

import crcmod.predefined

# constants
VERSION="1.0.0"
READ_RESPONSE_OVERHEAD  = 5 # <, LEN_MSB, LEN_LSB, CRC, >  # MZ: does NOT include ADDR
WRITE_RESPONSE_OVERHEAD = 2 # <, >
READY_POLL_LEN = 1
START = 0x3c # <
END   = 0x3e # >
WRITE = 0x80
CRC   = 0xff # for readability

# globals
crc8 = crcmod.predefined.mkPredefinedCrcFun('crc-8-maxim')
args = None 
lock = threading.Lock()

def parseArgs(argv):
    parser = argparse.ArgumentParser(
        description="GUI to test XS embedded spectrometers via SPI and FT232H adapter",
        epilog="Note: you may need to plug the FT232H USB cable in before connecting 12V to the spectrometer") # MZ: this seemed to help?
    parser.add_argument("--debug", action="store_true", help="output verbose debug messages")
    parser.add_argument("--ready-pin", type=str, default="D5", help="FT232H pin for DATA_READY (default D5)")
    parser.add_argument("--trigger-pin", type=str, default="D6", help="FT232H pin for TRIGGER (efault D6)")
    parser.add_argument("--paused", action="store_true", help="launch with acquisition paused")
    parser.add_argument("--gain", type=int, help="default gain (default 0, noting this is a 'FunkyFloat' where 0x01e7 = 1.9)", default=0)
    return parser.parse_args(argv[1:])

def debug(msg):
    if args.debug:
        print(f"DEBUG: {msg}")

## format a list or bytearray as "[ 0x00, 0x0a, 0xff ]"
def toHex(values):
    return "[ " + ", ".join([ f"0x{v:02x}" for v in values ]) + " ]"

## confirm the received CRC matches our computed CRC for the list or bytearray "data"
def checkCRC(crc_received, data):
    crc_computed = crc8(data)
    if crc_computed != crc_received:
        print(f"\nERROR *** CRC mismatch: received 0x{crc_received:02x}, computed 0x{crc_computed:02x}\n")

## given a list or bytearray of data elements, return the checksum
def computeCRC(data):
    return crc8(bytearray(data))

## 
# given a formatted SPI command of the form [START, L0, L1, ADDR, ...DATA..., CRC, END],
# return command with CRC replaced with the computed checksum of [L0..DATA] as bytearray
def fixCRC(cmd):
    if cmd is None or len(cmd) < 6 or cmd[0] != START or cmd[-1] != END:
        print(f"ERROR: fixCRC expects well-formatted SPI 'write' command: {cmd}")
        return

    index = len(cmd) - 2
    checksum = computeCRC(bytearray(cmd[1:index]))
    result = cmd[:index]
    result.extend([checksum, cmd[-1]])
    # debug(f"fixCRC: cmd {toHex(cmd)} -> result {toHex(result)}")
    return bytearray(result)

## @see ENG-0150-C section 3.2, "Configuration Set Response Packet"
def errorCodeToString(code):
    if   code == 0: return "SUCCESS"
    elif code == 1: return "ERROR_LENGTH"
    elif code == 2: return "ERROR_CRC"
    elif code == 3: return "ERROR_UNRECOGNIZED_COMMAND"
    else          : return "ERROR_UNDEFINED"

## 
# Given an existing list or bytearray, copy the contents into a new bytearray of
# the specified size. This is used to generate the "command" argument of a 
# SPI.write_readinto(cmd, response) call, as both buffers are expected to be of
# the same size.
#
# @see https://docs.circuitpython.org/en/latest/shared-bindings/busio/#busio.SPI.write_readinto
def buffer_bytearray(orig, size):
    new = bytearray(size)
    new[:len(orig)] = orig[:]
    return new

##
# Given an unbuffered "read" command (just the bytes we wanted to write, without
# trailing zeros for the read response), and the complete (buffered) response 
# read back (including leading junk from the command/write phase), parse out the
# actual response data and validate checksum.
#
# @para Example (reading FPGA version number)
# @verbatim
#              offset:    0     1     2     3     4     5     6     7     8     9    10    11    12    13    14    15    16    17   
#         explanation:    <    (_length_)  ADDR   >     <    (_length_)  ADDR  '0'   '2'   '.'   '1'   '.'   '2'   '3'   CRC    >   
#  unbuffered_command: [ 0x3c, 0x00, 0x01, 0x10, 0x3e ]
#    buffered_command: [ 0x3c, 0x00, 0x01, 0x10, 0x3e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 ] 
#   buffered_response: [  ?? ,  ?? ,  ?? ,  ?? ,  ?? , 0x3c, 0x00, 0x08, 0x10, 0x30, 0x32, 0x2e, 0x31, 0x2e, 0x32, 0x33, 0x83, 0x3e ] 
# unbuffered_response:                               [ 0x3c, 0x00, 0x08, 0x10, 0x30, 0x32, 0x2e, 0x31, 0x2e, 0x32, 0x33, 0x83, 0x3e ] 
#            crc_data:                                     [ 0x00, 0x08, 0x10, 0x30, 0x32, 0x2e, 0x31, 0x2e, 0x32, 0x33 ]
#       response_data:                                                       [ 0x30, 0x32, 0x2e, 0x31, 0x2e, 0x32, 0x33 ]
# @endverbatim
#
# @returns array of response payload bytes (everything after ADDR but before CRC)
# @note only used for SPI "read" commands ("write" commands are much simpler)
def decode_read_response(unbuffered_cmd, buffered_response, name=None, missing_echo_len=0):
    cmd_len = len(unbuffered_cmd)
    unbuffered_response = buffered_response[len(unbuffered_cmd) - missing_echo_len:]
    response_data_len = (unbuffered_response[1] << 8) | unbuffered_response[2]
    response_data = unbuffered_response[4 : 4 + response_data_len - 1]
    crc_received = unbuffered_response[-2]
    crc_data = unbuffered_response[1 : -2]
    checkCRC(crc_received, crc_data)

    if args.debug:
        print(f"decode_read_response({name}, missing={missing_echo_len}):")
        print(f"  unbuffered_cmd:      {toHex(unbuffered_cmd)}")
        print(f"  buffered_response:   {toHex(buffered_response)}")
        print(f"  cmd_len:             {cmd_len}")
        print(f"  unbuffered_response: {toHex(unbuffered_response)}")
        print(f"  response_data_len:   {response_data_len}")
        print(f"  response_data:       {toHex(response_data)}")
        print(f"  crc_received:        {hex(crc_received)}")
        print(f"  crc_data:            {toHex(crc_data)}")

    return response_data

## @returns response payload as string
def decode_read_response_str(unbuffered_cmd, buffered_response, name=None, missing_echo_len=0) -> str:
    return decode_read_response(unbuffered_cmd, buffered_response, name, missing_echo_len).decode()

## @returns little-endian response payload as uint16
def decode_read_response_int(unbuffered_cmd, buffered_response, name=None, missing_echo_len=0) -> int:
    response_data = decode_read_response(unbuffered_cmd, buffered_response, name, missing_echo_len)
    result = (response_data[1] << 8) | response_data[0] 
    if args.debug:
        print(f"  result:              {result}")
    return result

def decode_write_response(unbuffered_cmd, buffered_response, name=None, missing_echo_len=0):
    cmd_len = len(unbuffered_cmd)
    unbuffered_response = buffered_response[len(unbuffered_cmd) - missing_echo_len:]
    response_data_len = (unbuffered_response[1] << 8) | unbuffered_response[2]
    response_data = unbuffered_response[4 : 4 + response_data_len - 1]
    crc_received = unbuffered_response[-2]
    crc_data = unbuffered_response[1 : -2]
    checkCRC(crc_received, crc_data)

    if args.debug:
        print(f"decode_read_response({name}, missing={missing_echo_len}):")
        print(f"  unbuffered_cmd:      {toHex(unbuffered_cmd)}")
        print(f"  buffered_response:   {toHex(buffered_response)}")
        print(f"  cmd_len:             {cmd_len}")
        print(f"  unbuffered_response: {toHex(unbuffered_response)}")
        print(f"  response_data_len:   {response_data_len}")
        print(f"  response_data:       {toHex(response_data)}")
        print(f"  crc_received:        {hex(crc_received)}")
        print(f"  crc_data:            {toHex(crc_data)}")

    return response_data

# Simple verification function for Integer inputs
def fIntValidate(input):
    if input.isdigit():
        return True                        
    elif input == "":
        return True
    else:
        return False

# Class for the revision register
class cCfgString:

    frame = None
    SPI   = None

    ##
    # @param read_len: How many bytes of payload we expect to read back on 
    #                  SPIRead() calls, INCLUDING address, but NOT including 
    #                  those bytes already accounted for in READ_RESPONSE_OVERHEAD.
    #                  Defaults to 8 because that's what we use for the FPGA
    #                  version number (1 ADDR plus 7 ASCII).
    def __init__(self, name, row, value, address, read_len=8):
        self.name       = name
        self.row        = row
        self.value      = str(value)
        self.address    = int(address)
        self.read_len   = read_len

        self.label      = tk.Label(cCfgString.frame, text = name)
        self.label.grid(row=row, column=0)
        self.stringVar  = tk.StringVar(cCfgString.frame, str(value))
        self.entry      = tk.Entry(cCfgString.frame, textvariable=self.stringVar, width = 8)
        self.entry.grid(row=row, column=1)

    ##
    # Read a string from the FPGA. In this script, this is only used for the 
    # revision register.
    def SPIRead(self):
    
        # MZ: I seem able to read the 7-char FPGA version whether this length is
        #     set to 1 (original) or 8 (read_len)...why?

        # MZ: testing with CRC
        # unbuffered_cmd = [START, 0x00, self.read_len, self.address, END] # MZ: why does this command not get a CRC?  Should it?
        # buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + self.read_len)  # MZ: removed spurious "+1" in original

        unbuffered_cmd = fixCRC([START, 0x00, self.read_len, self.address, CRC, END]) 
        buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + self.read_len - 1)  

        buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
    
        # Write one buffer while reading the other
        cCfgString.SPI.write_readinto(buffered_cmd, buffered_response)

        # Decode the binary response into a string
        self.value = decode_read_response_str(unbuffered_cmd, buffered_response, self.name, missing_echo_len=1)

        # Set the text in the entry box
        self.stringVar.set(self.value)

    # This script currently does not write any string data to the FPGA via SPI.
    def SPIWrite(self):
        pass

    def Update(self):
        pass
        
# Class for configuration entries
class cCfgEntry:

    # Static class variables used for comms
    frame       = None
    validate    = None
    SPI         = None

    ##
    # Init class defines the objects name, default value, and FPGA Address
    # Creates a label and entry for the item.
    #
    # @param address:   7-bit getter "Code" from ENG-0150.  Note that as the
    #                   7-bit address is used for both read and write functions,
    #                   it does not have the "write" bit (0x80) set.
    # @param read_len:  How many bytes of payload we expect to read back on 
    #                   SPIRead() calls, INCLUDING address, but NOT including 
    #                   those bytes already accounted for in READ_RESPONSE_OVERHEAD.
    #                   Defaults to 3 because most entries are uint16 (ADDR, LSB, MSB).
    # @param write_len: How many bytes of payload we expect to write, including 
    #                   the ADDR byte, but not any of the bytes included in 
    #                   WRITE_RESPONSE_OVERHEAD. This value is what will be
    #                   passed as the "length" value at the start of the write 
    #                   frame header. Defaults to 3 because most FPGA integers
    #                   are uint16 (ADDR, LSB, MSB).
    def __init__(self, name, row, value, address, read_len=3, write_len=3):
        self.name       = name
        self.row        = row
        self.value      = int(value)
        self.address    = int(address) & 0x7f   # ensure 7-bit
        self.write_len  = write_len
        self.read_len   = read_len

        self.label      = tk.Label(cCfgEntry.frame, text = name)
        self.label.grid(row=row, column=0)
        self.stringVar  = tk.StringVar(cCfgEntry.frame, str(value))
        self.entry      = tk.Entry(cCfgEntry.frame, textvariable=self.stringVar, validate="key", validatecommand=(cCfgEntry.validate, '%S'), width = 5)
        self.entry.grid(row=row, column=1)

    ## Read an integer from the FPGA.
    def SPIRead(self):
        print("-----> THIS IS NEVER USED <-----")
        unbuffered_cmd = [START, 0, self.read_len, self.address, END] # MZ: changed 1 to self.read_len 
        buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + self.read_len) # MZ: removed +1 in orig
        buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
    
        # Write one buffer while reading the other
        SPI.write_readinto(buffered_cmd, buffered_response)
        self.value = decode_read_response_int(unbuffered_cmd, buffered_response, self.name)
    
        self.stringVar.set(str(self.value))

    ##
    # Write an integer to the FPGA.
    #
    # @verbatim
    # >><< CfgEntry[Integration Time].write: [ 0x3c, 0x00, 0x03, 0x91, 0x64, 0x00, 0x6a, 0x3e, 0x00, 0x00, 0x00 ] -> [ 0x3e, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x3c, 0x00, 0x3e, 0x3e ] 
    #                                           <    (_length_)  ADDR  (LSB Value)  CRC   >                             <     ?     ?     ?     ?     ?     ?     <  SUCCESS  >     >
    #                                  offset:  0     1     2     3     4     5     6     7                             0     1     2     3     4     5     6     7     8     9    10
    #                                           \_____________unbuffered_cmd______________/             MZ: I feel that \___this should be 8 bytes not 7____/
    #                                          \__________________________buffered_cmd_________________________/        \_________________________buffered_response____________________/
    # @endverbatim
    def SPIWrite(self):
    
        # Convert the int into bytes.
        txData = []
        txData      .append( self.value        & 0xff) # LSB
        txData      .append((self.value >>  8) & 0xff)
        if self.write_len > 3:
            txData  .append((self.value >> 16) & 0xff) # MSB
    
        unbuffered_cmd = [START, 0x00, self.write_len, self.address | WRITE] # MZ: replaced 3 with self.write_len
        unbuffered_cmd.extend(txData)
        unbuffered_cmd.extend([ computeCRC(unbuffered_cmd[1:]), END])
    
        # MZ: the -1 at the end was added as a kludge, because otherwise we find
        #     a redundant '>' in the last byte.  This seems a bug, due to the 
        #     fact that only 7 of the 8 unbuffered_cmd bytes are echoed back into
        #     the read buffer.
        buffered_response = bytearray(len(unbuffered_cmd) + WRITE_RESPONSE_OVERHEAD + 1 - 1) 
        buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
    
        SPI.write_readinto(buffered_cmd, buffered_response)
        result = int(buffered_response[-2]) 
        print(f">><< cCfgEntry[{self.name:16s}].write: {toHex(buffered_cmd)} -> {toHex(buffered_response)} (0x{result:02x} {errorCodeToString(result)})")

    # Fetch the data from the entry box and update it to the FPGA
    def Update(self):
        if self.value != int(self.stringVar.get()):
            self.value = int(self.stringVar.get())
            self.SPIWrite()
# End Class cCfgEntry

##
# Encapsulate both comboBoxes used to specify the combined PixelMode attribute.
#
# There is only ONE CfgCombo object instance; it is rendered as TWO comboBoxes 
# on-screen, allowing convenient setting of either of its two component values.
# The coupled values are read and written atomically.
class cCfgCombo:

    # Static class variables used for comms
    frame       = None
    SPI         = None

    ##
    # Init class defines the objects name, default value, and FPGA Address
    # Creates a label for the item.
    #
    # @param write_len: defaults to 2 (we're writing both ADDR and the 1-byte value)
    # @param read_len: defaults to 2 (we're reading both ADDR and the 1-byte value)
    def __init__(self, row, name, write_len=2, read_len=2):
        self.name       = name
        self.value      = 0x03         # default to 00000011b (both AD and OD set to 12-bit)
        self.address    = 0x2B
        self.row        = row
        self.write_len  = write_len
        self.read_len   = read_len

        self.labels     = []
        self.labels.append(tk.Label(cCfgCombo.frame, text = "AD Resolution"))
        self.labels[0].grid(row=row, column=0)
        self.labels.append(tk.Label(cCfgCombo.frame, text = "Output Resolution"))
        self.labels[1].grid(row=(row+1), column=0)
        self.stringVar  = []
        self.stringVar.append(tk.StringVar(cCfgCombo.frame))
        self.stringVar.append(tk.StringVar(cCfgCombo.frame))
        self.comboBox = []
        self.comboBox.append(ttk.Combobox(cCfgCombo.frame, textvariable = self.stringVar[0], values=('10', '12'), state='readonly', width = 4))
        self.comboBox[0].grid(row=row, column=1)
        self.comboBox[0].current(1)
        self.comboBox.append(ttk.Combobox(cCfgCombo.frame, textvariable = self.stringVar[1], values=('10', '12'), state='readonly', width = 4))
        self.comboBox[1].grid(row=(row+1), column=1)
        self.comboBox[1].current(1)

    # Read single byte from the FPGA.
    def SPIRead(self):
        print("-----> THIS IS NEVER USED <-----")
        unbuffered_cmd = [START, 0, self.read_len, self.address, END]
        buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + self.read_len) # MZ: orig had bytearray(14) (3 bytes larger)
        buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
    
        SPI.write_readinto(buffered_cmd, buffered_response)
    
        self.value = decode_read_response_int(unbuffered_cmd, buffered_response, self.name)
        self.stringVar.set(str(self.value))
            
    def SPIWrite(self):
        unbuffered_cmd = fixCRC([START, 0, self.write_len, self.address | WRITE, self.value, CRC, END])
        buffered_response = bytearray(len(unbuffered_cmd) + WRITE_RESPONSE_OVERHEAD + self.write_len - 1)  # MZ: kludge (added -1, same as required for cCfgEntry.SPIWrite)
        buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
        SPI.write_readinto(buffered_cmd, buffered_response) 

    def Update(self):
        newValue = 0
        if self.stringVar[0].get() == '12':
            newValue += 2
        if self.stringVar[1].get() == '12':
            newValue += 1
        if self.value != newValue:
            self.value = newValue
            self.SPIWrite()
# End Class cCfgCombo

# EEPROM Control Window Class (not instantiated until window opened by button)
class cWinEEPROM:
    
    def __init__(self, SPI, intValidate):
        self.SPI = SPI
        self.root = tk.Tk()
        self.root.title("EEPROM Util")
        self.frame      = tk.Frame(self.root)
        self.valStrings = []
        self.valEntries = []
        for x in range(0, 64):
            self.valStrings.append(tk.StringVar(self.frame))
        for x in range(0, 64):
            self.valEntries.append(tk.Entry(self.frame, textvariable = self.valStrings[x], width = 5))
        for x in range(0, 8):
            for y in range(0, 8):
                self.valEntries[((x*8)+y)].grid(row=x, column=y)

        self.pageStr        = tk.StringVar(self.frame, str(0))
        self.pageLbl        = tk.Label(self.frame, text = 'EEPROM Page').grid(row=8, column=1)
        self.pageEnt        = tk.Entry(self.frame, textvariable = self.pageStr, validate="key", validatecommand=(intValidate, '%S'), width = 5)
        self.pageEnt.grid(row=8, column=2)

        self.readButton     = tk.Button(self.frame, text='Read Page', command=self.EEPROMRead)
        self.readButton.grid(row=8, column=4)
        self.writeButton    = tk.Button(self.frame, text='Write Page', command=self.EEPROMWrite)
        self.writeButton.grid(row=8, column=6)

        col_count, row_count = self.frame.grid_size()
        for column in range(col_count):
            self.frame.grid_columnconfigure(column, minsize = 75)
        for row in range(row_count):
            self.frame.grid_rowconfigure(row, minsize=30)

        self.frame.pack()
        self.EEPROMRead()
        self.root.mainloop()

    ##
    # @para API (ENG-0150-C)
    #
    # 5.3 Read EEPROM
    #
    # Send the command to get the FPGA to read the EEPROM:
    #   [0x3C, 0x00, 0x02, 0xB0, 0x4Y, CRC, 0x3E]    Where Y is the page number of the EEPROM you wish to read.
    #  
    # Wait until SPEC_BUSY is deasserted.
    #  
    # Read back the buffer:
    #   [0x3C, 0x00, 0x01, 0x31, 0x24, 0x3E] (Followed by enough bytes (64) of padding to read all the buffer out).
    #    START \_length_/  ADDR  CRC  END   MZ: why does an EEPROM 'read' command get a CRC, when cCfgString.SPIRead() does not?
    #
    # @warning MZ: 0x4Y only supports 10 EEPROM pages: eventual schema should support 512 pages (okay for now)
    def EEPROMRead(self):
        page = int(self.pageStr.get())

        with lock:
            # MZ: is 0xb0 treated as a 'write' or a 'read'?  It has the 0x80 bit high...
            #     therefore, treating as a WRITE, therefore, reading response

            # length is 0x0002 because it's the length of (addr, page_offset), not 
            # the length of the page we're intending to read (which would be 0x0020)
            # (this is a WRITE command to setup the subsequent READ operation)
            unbuffered_cmd = fixCRC([START, 0, 2, 0xB0, (0x40 + page), CRC, END])
            buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + 1)  
            buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))

            self.SPI.write_readinto(buffered_cmd, buffered_response)

            # MZ: I tried reading a "write response" after the 0xb0 (EEPROM_READ_REQUEST) 
            #     with its one-byte payload (EEPROM page index), but all I get is a zero 
            #     followed by a run of START bytes.
            #
            # result = int(buffered_response[-2]) 
            # print(f">><< EEPROMRead: {toHex(buffered_cmd)} -> {toHex(buffered_response)} (0x{result:02x} {errorCodeToString(result)})")
            print(f">> EEPROMRead: {toHex(buffered_cmd)} -> {toHex(buffered_response)}")

            # MZ: API says "wait for SPEC_BUSY to be deasserted...why aren't we doing that?
            time.sleep(0.01) # empirically determined 10ms delay

            # MZ: original (and API) have length 1 here...why?  Should this not be at least 65 (addr + data)? 
            unbuffered_cmd = fixCRC([START, 0, 65, 0x31, CRC, END]) 
            buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + 64) # MZ: including kludged -1
            buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
            self.SPI.write_readinto(buffered_cmd, buffered_response)

        values = decode_read_response(unbuffered_cmd, buffered_response, "EEPROMRead", missing_echo_len=1)
        debug(f"decoded {len(values)} values from EEPROM")

        # update to form
        for x in range(max(64, len(values))):
            self.valStrings[x].set(f"{values[x]:02x}")

    def EEPROMWrite(self):
        page        = int(self.pageStr.get())
        command     = bytearray(7)
        EEPROMWrCmd = bytearray(70)
        EEPROMWrCmd[0:3] = [START, 0x00, 0x41, 0xB1]
        for x in range(0, 64):
            EEPROMWrCmd[x+4] = int(self.valStrings[x].get(), 16)

        EEPROMWrCmd[68] = 0xFF
        EEPROMWrCmd[69] = END
        self.SPI.write(EEPROMWrCmd, 0, 70)
        print(f">> EEPROM.write {EEPROMWrCmd}")
        command = [START, 0x00, 0x02, 0xB0, page | WRITE, CRC, END]
        self.SPI.write(command, 0, 7)
        print(f">> EEPROM.write {toHex(command)}")
# End Class cWinEEPROM

# Class container for the area scan window
class cWinAreaScan:

    def __init__(self, SPI, ready, trigger, lineCount, columnCount):
        self.SPI     = SPI
        self.ready   = ready
        self.trigger = trigger
        self.root    = tk.Tk()
        self.root.title("Area Scan")
        self.frame   = tk.Frame(self.root)
        self.canvas  = tk.Canvas(self.frame, bg="black", height=lineCount, width=columnCount)
        #This doesn't work and I don't know why /sadface
        #   self.image   = tk.PhotoImage(height=lineCount, width=columnCount)
        #   self.canvas.create_image((columnCount/2, lineCount/2), image=self.image, state="normal")
        self.frame.pack()
        self.canvas.pack()
        # Enable Area Scan
        command = [START, 0x00, 0x03, 0x92, 0x00, 0x10, CRC, END]
        self.SPI.write(command, 0, 8)
        # Send a trigger
        self.trigger.value = True
        # Wait until the data is ready
        SPIBuf  = bytearray(2)
        for y in range(1, lineCount):
            x = 0
            while not self.ready.value:
                pass
            self.SPI.readinto(SPIBuf, 0, len(SPIBuf))
            pixel = (SPIBuf[0] << 8) + SPIBuf[1]
            print("Reading line number: ", SPIBuf[0], SPIBuf[1], pixel);
            for x in range(1, columnCount):
                self.SPI.readinto(SPIBuf, 0, 2)
                pixel = (((SPIBuf[0] << 8) + SPIBuf[1]) >> 4)
                pixelHex = hex(pixel)
                pixelHex = pixelHex[2:].zfill(2)
                color = "#" + pixelHex + pixelHex + pixelHex
                #self.image.put(color, (x,y))
                self.canvas.create_line(x-1, y, x, y, fill=color, width=1)
                
        # Clear the trigger
        self.trigger.value = False
        # Disable Area Scan
        command = [START, 0x00, 0x03, 0x92, 0x00, 0x00, CRC, END]
        self.SPI.write(command, 0, 8)
        self.root.mainloop()

# Class container for the main window and all of its elements
class cWinMain:

    def __init__(self, SPI, ready, trigger, intValidate):
        # Register the handles
        self.SPI        = SPI
        self.ready      = ready
        self.trigger    = trigger
        # Create and title a window
        self.root = tk.Tk()
        self.root.title(f"SPI SIG Version {VERSION}")
        # Pass the SPI Comm handle
        cCfgString.SPI = self.SPI
        cCfgEntry.SPI  = self.SPI
        cCfgCombo.SPI  = self.SPI
        # Register the integer validation callback
        self.cbIntValidate = self.root.register(intValidate)
        # Pass it to the Entry class
        cCfgEntry.validate = self.cbIntValidate        
        # Create a frame for the configuration objects
        self.configFrame = tk.Frame(self.root)
        self.configFrame.grid(row=0, column=0)
        # Pass it to the config object classes
        cCfgString.frame = self.configFrame
        cCfgEntry.frame  = self.configFrame
        cCfgCombo.frame  = self.configFrame
        # Create frame for drawing. 
        self.drawFrame= tk.Frame(self.root)
        self.canvas = tk.Canvas(self.drawFrame, bg="black", height=810, width=1200)
        self.canvas.pack()
        self.drawFrame.grid(row=0, column=1)

        ########################################################################
        # Create all of the config entries        
        ########################################################################
        
        # MZ: In ENG-0150-C, the following codes are listed in the "Command Table":
        #
        # Description               Getter  Setter  Get Len Set Len Notes
        # ------------------------- ------- ------- ------- ------- -------- 
        # FPGA Version              0x10    ----    1       --      "xx.y.zz"                           # MZ: should getter payload bytes be 8 (incl
        # Integration Time          0x11    0x91    1       4       24-bit millisec                     # MZ: should getter payload bytes be 4?
        # Config Register           0x12    0x92    1       3       16-bit register                     # MZ: should getter payload bytes be 3?
        # Black Level               0x13    0x93    1       3       16-bit offset                       # MZ: should getter payload bytes be 3?
        # Gain dB                   0x14    0x94    1       3       16-bit "FunkyFloat"                 # MZ: should getter payload bytes be 3?
        # Detector Resolution       0x2b    0xab    1       2       Bit[1]: AD 12/10, bit[0]: OD 12/10  # MZ: should getter payload bytes be 2?
        # Buffered EEPROM Page      0x31    0xb1    1       65      64-byte page                        # MZ: should getter payload bytes be 65?
        # Start Line                0x50    0xd0    1       3       16-bit line                         # MZ: should getter payload bytes be 3?
        # Stop Line                 0x51    0xd1    1       3       16-bit line                         # MZ: should getter payload bytes be 3?
        # Start Column              0x52    0xd2    1       3       16-bit column                       # MZ: should getter payload bytes be 3?
        # Stop Column               0x53    0xd3    1       3       16-bit column                       # MZ: ENG-0150-C says setter is 0xD4!
        #
        # Additional: 0xb0 is used for BOTH "write FPGA EEPROM buffer to EEPROM"
        #                               AND "read EEPROM data to FPGA buffer"; not sure how that works out
        
        # Empty list for the config objects # Name              row   value     address
        self.configObjects = []             # ----------------- ----- --------- -------
        # Create an object for the FPGA Revision (special case, we want this box read only)
        self.configObjects.append(cCfgString("FPGA Revision"   , 0 , "00.0.00", 0x10, read_len=8)) 
        self.configObjects[0].entry.config(state='disabled', disabledbackground='light grey', disabledforeground='black')
        self.configObjects.append(cCfgEntry("Integration Time" , 1  , 100     , 0x11, write_len=4, read_len=4)) # MZ: integration time is 24-bit
        self.configObjects.append(cCfgEntry("Black Level"      , 2  , 0       , 0x13))
        self.configObjects.append(cCfgEntry("Detector Gain"    , 3  ,args.gain, 0x14))
        self.configObjects.append(cCfgEntry("Start Line 0"     , 4  , 250     , 0x50)) # Region 0
        self.configObjects.append(cCfgEntry("Stop Line 0"      , 5  , 750     , 0x51))
        self.configObjects.append(cCfgEntry("Start Column 0"   , 6  , 12      , 0x52))
        self.configObjects.append(cCfgEntry("Stop Column 0"    , 7  , 1932    , 0x53))
        self.configObjects.append(cCfgEntry("Start Line 1"     , 8  , 0       , 0x54)) # Region 1 (MZ: not in ENG-0150)
        self.configObjects.append(cCfgEntry("Stop Line 1"      , 9  , 0       , 0x55))
        self.configObjects.append(cCfgEntry("Start Column 1"   , 10 , 0       , 0x56))
        self.configObjects.append(cCfgEntry("Stop Column 1"    , 11 , 0       , 0x57))
        self.configObjects.append(cCfgEntry("Desmile Offset"   , 12 , 0       , 0x58)) # Experimental (MZ: not in ENG-0150...also, not sure one int1

        # Add the AD/OD combo boxes
        self.configObjects.append(cCfgCombo(13, "PixelMode"))

        self.configMap = {}
        for obj in self.configObjects:
            self.configMap[obj.name] = obj.row

        # Add the buttons
        self.btnCapture  = tk.Button(self.configFrame, text='Update', command=self.FPGAUpdate)
        self.btnCapture.grid(row=16, column=0)
        self.btnEEPROM   = tk.Button(self.configFrame, text='EEPROM', command=self.openEEPROM)
        self.btnEEPROM.grid(row=17, column=0)
        self.btnAreaScan = tk.Button(self.configFrame, text='Area Scan', command=self.openAreaScan)
        self.btnAreaScan.grid(row=16, column=1)

        self.textStart = tk.StringVar()
        self.textStart.set("???")
        self.btnStart = tk.Button(self.configFrame, textvariable=self.textStart, command=self.toggleStart)
        self.btnStart.grid(row=17, column=1)
        # Resize the grid
        col_count, row_count = self.configFrame.grid_size()
        self.configFrame.grid_columnconfigure(0, minsize=120)
        self.configFrame.grid_columnconfigure(1, minsize=120)
        for row in range(row_count):
            self.configFrame.grid_rowconfigure(row, minsize=30)
        
        debug("writing initial values to FPGA")
        self.FPGAInit()

        self.firstSpectrum = True
       
        self.stop() if args.paused else self.start()

        self.root.mainloop()

        debug("exiting")

    def start(self):
        with lock:
            debug("starting acquisition loop")
            self.textStart.set("Stop")
            self.acquireActive = True
            self.root.after(10, self.Acquire)

    def stop(self):
        with lock:
            debug("pausing acquisition loop")
            self.textStart.set("Start")
            self.acquireActive = False

    def toggleStart(self):
        self.stop() if self.acquireActive else self.start()

    def getValue(self, name):
        index = self.configMap[name]
        return self.configObjects[index].value

    def Acquire(self):
        with lock:
            if not self.acquireActive:
                return

            # debug("Acquire: raising trigger")
            self.trigger.value = True

            # debug("Acquire: blocking on DATA_READY")
            while not self.ready.value:
                pass

            # debug("Acquire: releasing trigger")
            self.trigger.value = False

            # Read in the spectra
            SPIBuf  = bytearray(2)
            spectra = []
            while self.ready.value:
                self.SPI.readinto(SPIBuf, 0, 2)
                pixel = (SPIBuf[0] << 8) + SPIBuf[1]
                spectra.append(pixel)
            # debug(f"Acquire: read {len(spectra)} pixels") # MZ: by default we get back 1000, which is correctly 1500 - 500 

        region0 = self.getValue("Stop Column 0") - self.getValue("Start Column 0")
        region1 = self.getValue("Stop Column 1") - self.getValue("Start Column 1")
        region1Active = self.getValue("Stop Line 1") != 0

        desmileOffset = self.getValue("Desmile Offset")
        maxvalue0 = 0
        minvalue0 = 65536
        maxvalue1 = 0
        minvalue1 = 65536
        spectraBinned0 = []
        spectraBinned1 = []

        if self.firstSpectrum:
            debug(f"len(spectra) {len(spectra)}, desmileOffset {desmileOffset}, region0 {region0}")
            self.firstSpectrum = False

        try:
            for x in range(desmileOffset, region0, 2):
                if x < len(spectra):
                    pixel = int((spectra[x-1] + spectra[x]) / 2)
                    if pixel > maxvalue0:
                        maxvalue0 = pixel
                    if pixel < minvalue0:
                        minvalue0 = pixel
                    spectraBinned0.append(pixel)

            if region1Active:
                for x in range((region0+1), (region0+region1), 2):
                    pixel = int((spectra[x-1] + spectra[x]) / 2)
                    if pixel > maxvalue1:
                        maxvalue1 = pixel
                    if pixel < minvalue1:
                        minvalue1 = pixel
                    spectraBinned1.append(pixel)
        except:
            debug("ignoring graph error")
            return

        # Draw the graph
        scale0 = maxvalue0 - minvalue0

        WIDTH=1160
        HEIGHT=340
        LEFT=40
        TOP=380
        TOP2=790

        if scale0 != 0:
            midvalue = int(minvalue0 + (scale0/2))
            self.canvas.delete("all") # delete previous contents
            self.canvas.create_text(20,20,text=str(maxvalue0), fill="white")
            self.canvas.create_text(20,200,text=str(midvalue), fill="white")
            self.canvas.create_text(20,380,text=str(minvalue0), fill="white")
            self.canvas.create_line(0, 405, 1400, 405, fill="light grey", width=10)
            spectraCount = len(spectraBinned0)
            for x in range(1, spectraCount):
                x0 = int((x/spectraCount)*WIDTH) + LEFT
                y0 = TOP - int(((spectraBinned0[(x-1)]-minvalue0)/scale0)*HEIGHT)
                x1 = int(((x+1)/spectraCount)*WIDTH) + LEFT
                y1 = TOP - int(((spectraBinned0[x]-minvalue0)/scale0)*HEIGHT)
                self.canvas.create_line(x0, y0, x1, y1, fill="green", width=1)
        if region1Active:
            scale1 = maxvalue1 - minvalue1
            midvalue = int(minvalue1 + (scale1/2))
            self.canvas.create_text(20,430,text=str(maxvalue1), fill="white")
            self.canvas.create_text(20,610,text=str(midvalue), fill="white")
            self.canvas.create_text(20,790,text=str(minvalue0), fill="white")
            spectraCount = len(spectraBinned1)
            for x in range(1, spectraCount):
                x0 = int((x/spectraCount)*WIDTH) + LEFT
                y0 = TOP2 - int(((spectraBinned1[(x-1)]-minvalue1)/scale1)*HEIGHT)
                x1 = int(((x+1)/spectraCount)*WIDTH) + LEFT
                y1 = TOP2 - int(((spectraBinned1[x]-minvalue1)/scale1)*HEIGHT)
                self.canvas.create_line(x0, y0, x1, y1, fill="blue", width=1)

        if (self.acquireActive):
            self.root.after(10, self.Acquire)

    def FPGAInit(self):
        debug("performing FPGA Init")
        response = bytearray(READY_POLL_LEN)
        # Read out any errant data
        while self.ready.value:
            self.SPI.readinto(response, 0, READY_POLL_LEN)
        # Fetch the revision from the FPGA
        self.configObjects[0].SPIRead()
        # Iterate through each of the config objects and write to the FPGA
        for x in range(1, len(self.configObjects)):
            self.configObjects[x].SPIWrite()

    def FPGAUpdate(self):
        debug("performing FPGA Update")
        response = bytearray(READY_POLL_LEN)
        # Read out any errant data
        while self.ready.value:
            self.SPI.readinto(response, 0, READY_POLL_LEN)
        # Iterate through each of the config objects and update to the FPGA if necessary
        for cfgObj in self.configObjects:
            cfgObj.Update()

        self.firstSpectrum = True

    def openEEPROM(self):
        debug("opening EEPROM")
        with lock:
            self.acquireActive = False
        self.winEEPROM = cWinEEPROM(self.SPI, self.cbIntValidate)

    def openAreaScan(self):
        debug("opening Area Scan")
        with lock:
            self.acquireActive = False
        # Give time for the last acquisition to complete
        time.sleep(0.1)
        lineCount   = self.getValue("Stop Line 0") - self.getValue("Start Line 0")
        columnCount = self.getValue("Stop Column 0") - self.getValue("Start Column 0")
        self.winAreaScan   = cWinAreaScan(self.SPI, self.ready, self.trigger, lineCount, columnCount)
        with lock:
            self.acquireActive = True
        self.root.after(10, self.Acquire)

# End Class cWinMain

###############Begin Main################

# parse command-line args (user may need different trigger/ready pins)
args = parseArgs(sys.argv)

# Initialize the SPI bus on the FT232H
SPI = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# Initialize D5 as the ready signal
ready = digitalio.DigitalInOut(getattr(board, args.ready_pin.upper()))
ready.direction = digitalio.Direction.OUTPUT

# Initialize D6 as the trigger
trigger = digitalio.DigitalInOut(getattr(board, args.trigger_pin.upper()))
trigger.direction = digitalio.Direction.OUTPUT
trigger.value = False

# Take control of the SPI Bus
while not SPI.try_lock():
    pass

# Configure the SPI bus
TWENTY_MHZ = 20000000
SPI.configure(baudrate=TWENTY_MHZ, phase=0, polarity=0, bits=8)

# Create the main window and pass in the handles
winSIG = cWinMain(SPI, ready, trigger, fIntValidate)
