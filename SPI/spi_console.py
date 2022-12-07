"""
This is a command-line script provided to test Wasach Photonics Series-XS (SiG)
spectrometers using a SPI interface.

It provides a real-time GUI allowing the user to control integration time, 
gain (dB), vertical ROI and other acquisition parameters, while graphing and
collected spectra. 

Features include:

- reads and parses key fields from the EEPROM, including wavecal in wavelength 
  and wavenumber (may be disabled for FW in which EEPROM access is unsupported)
- save measuremnts as .csv
- add on-screen traces for visual comparison
- "test mode" for automated unit QC
- resizable graph with pan/zoom

See --help for command-line options.

SPI API
    The Wasatch Photonics SPI API is documented in Engineering Document ENG-0150,
    available from the company on request (but largely inferrable from this 
    script).

Hardware Dependencies
    Because personal computers do not have a user-accessible SPI connector, the
    script assumes usage of an Adafruit FT232H USB-to-SPI adapter:

    https://www.adafruit.com/product/2264

Test Mode
    The script has a special mode for quickly performing a timing test and bulk
    data collection from a single connected spectrometer.  When running in this 
    mode, the script will:

    - disable the GUI (real-time graphing enacts a speed penalty)
    - automatically collect --test-count measurements at the configured 
      integration time, gain and vertical ROI
    - compute individual and aggregate timing metrics on each measurement
    - save a test report under data/ containing all measurements and metrics

Troubleshooting
    - You may need to plug the FT232H USB cable in before connecting 12V to the 
      spectrometer.
    - If the script seems to "freeze" at startup, make sure you're setting your 
      READY/TRIGGER pins correctly, both on the FT232H and cmd-line args

Deprecated Features
    Area Scan, Horizontal ROI, Multiple ROI, Desmile, Black Level, Pixel Mode and
    EEPROM Write features have been removed for simplicity, as they are not being 
    actively tested at this time.  They can be restored by borrowing and updating
    the relevant code from earlier commits (see tag spi_console_removing_unused).

TODO
    - move all the classes (and all globals) to a TestFixture class
"""

################################################################################
#                                                                              #
#                               Dependencies                                   #
#                                                                              #
################################################################################

import tkinter as tk
import tkinter.ttk as ttk

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import crcmod.predefined

import threading
import argparse
import datetime
import platform
import logging
import struct
import math
import time
import json
import sys
import os

from statistics import median

def checkZadig():
    if platform.system() == "Windows":
        print("Ensure you've followed the Zadig process in https://github.com/WasatchPhotonics/ENLIGHTEN/blob/main/README_SPI.md")

runnable = True
try:
    os.environ["BLINKA_FT232H"] = "1"
    import board
    import digitalio
    import busio
except RuntimeError as ex:
    print("No FT232H connected.\n")
    checkZadig()
    runnable = False
except ValueError as ex:
    print("If you are receiving 'no backend available' errors, try the following:")
    print("MacOS:  $ export DYLD_LIBRARY_PATH=/usr/local/lib")
    print("Linux:  $ export LD_LIBRARY_PATH=/usr/local/lib")
    runnable = False
except FtdiError as ex:
    print("No FT232H connected.\n")
    checkZadig()
    runnable = False

################################################################################
#                                                                              #
#                                 Constants                                    #
#                                                                              #
################################################################################

VERSION = "1.4.1"
READ_RESPONSE_OVERHEAD  = 5 # <, LEN_MSB, LEN_LSB, CRC, >  # does NOT include ADDR
WRITE_RESPONSE_OVERHEAD = 2 # <, >
READY_POLL_LEN = 2          # 1 seems to work
START = 0x3c                # <
END   = 0x3e                # >
WRITE = 0x80                # bit changing opcodes from 'getter' to 'setter'
CRC   = 0xff                # for readability
DATA_DIR = "data"           # under the current working directory
MIN_DELAY_MS = 100          # varies by hardware / OS -- this is to ensure responsive GUI, even with --debug

# these acquisition are not currently exposed by the GUI 
HARDCODED_PARAMETERS = [
   # addr value len name
   # ---- ----- --- -----------
    (0x2B,    3, 2, "Pixel Mode"),
    (0x13,    0, 3, "Black Level"),
    (0x52,   12, 3, "Start Column 0"),     
    (0x53, 1932, 3, "Stop Column 0"),
    (0x54,    0, 3, "Start Line 1"),
    (0x55,    0, 3, "Stop Line 1"),
    (0x56,    0, 3, "Start Column 1"),
    (0x57,    0, 3, "Stop Column 1"),
    (0x58,    0, 3, "Desmile") 
]

################################################################################
#                                                                              #
#                                  Globals                                     #
#                                                                              #
################################################################################

crc8 = crcmod.predefined.mkPredefinedCrcFun('crc-8-maxim')
lock = threading.Lock()
args = None

def parseArgs(argv):

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
        pass

    parser = argparse.ArgumentParser(
        description="GUI to test Wasatch Photonics Series-XS (SiG) embedded spectrometers via SPI and FT232H adapter",
        epilog=globals()['__doc__'],
        formatter_class=CustomFormatter)

    parser.add_argument("--ready-pin",           type=str,   default="D5",         help="FT232H pin for DATA_READY")
    parser.add_argument("--trigger-pin",         type=str,   default="D6",         help="FT232H pin for TRIGGER")
    parser.add_argument("--baud-mhz",            type=int,   default=10,           help="baud rate in MHz")
    parser.add_argument("--integration-time-ms", type=int,   default=3,            help="startup integration time in ms")
    parser.add_argument("--gain-db",             type=int,   default=24,           help="startup gain in INTEGRAL dB (24 sent as FunkyFloat 0x1800)")
    parser.add_argument("--start-line",          type=int,   default=250,          help="startup ROI top")
    parser.add_argument("--stop-line",           type=int,   default=750,          help="startup ROI bottom")
    parser.add_argument("--delay-ms",            type=int,   default=MIN_DELAY_MS, help="delay between acquisitions (zero for --test)")
    parser.add_argument("--test-count",          type=int,   default=100,          help="collect this many spectra in --test")
    parser.add_argument("--test-ramp-start",     type=int,   default=3,            help="start ramp at this integration time")
    parser.add_argument("--test-ramp-stop",      type=int,   default=10,           help="stop ramp at this integration time")
    parser.add_argument("--test-ramp-incr",      type=int,   default=1,            help="increment ramp at this integration time")
    parser.add_argument("--throwaways",          type=int,   default=3,            help="automatic throwaway measurements")
    parser.add_argument("--block-size",          type=int,   default=256,          help="block size for --fast SPI reads")
    parser.add_argument("--pixels",              type=int,   default=1920,         help="how many pixels to use if --no-eeprom")
    parser.add_argument("--batch-count",         type=int,   default=10,           help="how many spectra to save when clicking 'batch'")
    parser.add_argument("--excitation-nm",       type=float, default=-1,           help="laser excitation wavelength (creates wavenumber axis if positive)")
    parser.add_argument("--save",                type=bool,  default=True,         help="save each spectrum (--no-save to disable)", action=argparse.BooleanOptionalAction)
    parser.add_argument("--eeprom",              type=bool,  default=True,         help="load and act on EEPROM configuration (--no-eeprom to disable)", action=argparse.BooleanOptionalAction)
    parser.add_argument("--eeprom-file",         type=str,                         help="path to JSON file containing virtual EEPROM contents")
    parser.add_argument("--test-linearity",      action="store_true",              help="after data collection, test linearity by ramping integration time")
    parser.add_argument("--paused",              action="store_true",              help="launch with acquisition paused")
    parser.add_argument("--debug",               action="store_true",              help="output verbose debug messages")
    parser.add_argument("--test",                action="store_true",              help="run one test then exit")
    parser.add_argument("--ext-trigger",         action="store_true",              help="don't send triggers via FT232H (requires external function generator)")

    args = parser.parse_args(argv[1:])

    # positive --delay-ms is required for interactive GUI, but zeroed for --test
    if args.test:
        args.paused = True
        args.delay_ms = 0
    elif args.delay_ms < MIN_DELAY_MS:
        print(f"WARNING: interactive GUI recommends --delay-ms of at least {MIN_DELAY_MS}ms")
        args.delay_ms = MIN_DELAY_MS

    return args

def debug(msg):
    if args.debug:
        print(f"{timestamp()} DEBUG: {msg}")

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
def errorCodeToString(code) -> str:
    if   code == 0: return "SUCCESS"
    elif code == 1: return "ERROR_LENGTH"
    elif code == 2: return "ERROR_CRC"
    elif code == 3: return "ERROR_UNRECOGNIZED_COMMAND"
    else          : return "ERROR_UNDEFINED"

## @param response (Input): the last 3 bytes of the device's response to a SPI write command
def validateWriteResponse(response) -> str:
    if len(response) != 3:
        return f"invalid response length: {response}"
    if response[0] != START:
        return f"invalid response START marker: {response}"
    if response[2] != END:
        return f"invalid response END marker: {response}"
    return errorCodeToString(response[1])

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

def decode_write_response_UNUSED(unbuffered_cmd, buffered_response, name=None, missing_echo_len=0):
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

def send_command(SPI, ready, address, value, write_len, name=""):
    txData = []
    txData      .append( value        & 0xff) # LSB
    if write_len > 2:
        txData  .append((value >>  8) & 0xff)
    if write_len > 3:
        txData  .append((value >> 16) & 0xff) # MSB

    unbuffered_cmd = [START, 0x00, write_len, address | WRITE]
    unbuffered_cmd.extend(txData)
    unbuffered_cmd.extend([ computeCRC(unbuffered_cmd[1:]), END])

    # MZ: the -1 at the end was added as a kludge, because otherwise we find
    #     a redundant '>' in the last byte.  This seems a bug, due to the
    #     fact that only 7 of the 8 unbuffered_cmd bytes are echoed back into
    #     the read buffer.
    buffered_response = bytearray(len(unbuffered_cmd) + WRITE_RESPONSE_OVERHEAD + 1 - 1)
    buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))

    with lock:
        flushInputBuffer(ready, SPI)
        SPI.write_readinto(buffered_cmd, buffered_response)

    errorMsg = validateWriteResponse(buffered_response[-3:])
    print(f">><< cCfgEntry[{name:16s}].write: {toHex(buffered_cmd)} -> {toHex(buffered_response)} ({errorMsg})")

# Simple verification function for Integer inputs
def fIntValidate(input):
    if input.isdigit():
        return True
    elif input == "":
        return True
    else:
        return False

def flushInputBuffer(ready, spi):
    count = 0
    junk = bytearray(READY_POLL_LEN)
    # debug("flushing input buffer...")
    while ready.value:
        spi.readinto(junk)
        count += 1
    if count > 0:
        debug(f"flushed {count} bytes from input buffer")

def waitForDataReady(ready):
    # debug("waiting for data ready...")
    while not ready.value:
        pass
    # debug("...got data ready")

##
# Convert a (potentially) floating-point value into the big-endian 16-bit "Funky
# Float" used for detector gain in the FPGA on both Hamamatsu and IMX sensors.
#
# @see https://wasatchphotonics.com/api/Wasatch.NET/class_wasatch_n_e_t_1_1_funky_float.html
def gain_to_ff(gain):
    msb = int(round(gain, 5)) & 0xff
    lsb = int((gain - msb) * 256) & 0xff
    raw = (msb << 8) | lsb
    debug(f"gain_to_ff: {gain:0.3f} -> dec {raw} (0x{raw:04x})")
    return raw

def timestamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S.%f")

def sleep_ms(ms):
    ms = int(round(ms))
    sec = ms / 1000.0
    debug(f"sleeping {ms} ms")
    time.sleep(sec)

################################################################################
#                                                                              #
#                                 cCfgString                                   #
#                                                                              #
################################################################################

## Used to read FPGA revision
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
        with lock:
            cCfgString.SPI.write_readinto(buffered_cmd, buffered_response)

        # Decode the binary response into a string
        self.value = decode_read_response_str(unbuffered_cmd, buffered_response, self.name, missing_echo_len=1)

        # Set the text in the entry box
        self.stringVar.set(self.value)

        debug(f"{self.name} = {self.value}")

    # This script currently does not write any string data to the FPGA via SPI.
    def SPIWrite(self):
        pass

    def Update(self, force=False) -> bool:
        return False

################################################################################
#                                                                              #
#                                 cCfgEntry                                    #
#                                                                              #
################################################################################

## Used to write integral values
class cCfgEntry:

    # Static class variables used for comms
    frame       = None
    validate    = None
    SPI         = None
    ready       = None

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

    ## added because gain value sent over-the-wire differs from what's shown on the GUI
    def getTransmitValue(self):
        if self.name == "Detector Gain":
            return gain_to_ff(self.value)
        return self.value

    ## Read an integer from the FPGA.
    def SPIRead(self):
        print("-----> THIS IS NEVER USED <-----")
        unbuffered_cmd = [START, 0, self.read_len, self.address, END] # MZ: changed 1 to self.read_len
        buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + self.read_len) # MZ: removed +1 in orig
        buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))

        # Write one buffer while reading the other
        with lock:
            self.SPI.write_readinto(buffered_cmd, buffered_response)
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
        send_command(SPI       = self.SPI,
                     ready     = self.ready,
                     address   = self.address,
                     value     = self.getTransmitValue(),
                     write_len = self.write_len,
                     name      = self.name)

    ## Fetch the data from the entry box and update it to the FPGA
    def Update(self, force=False) -> bool:
        if self.value != int(self.stringVar.get()) or force:
            self.value = int(self.stringVar.get())
            self.SPIWrite()
            return True
        return False

    # Override the value in the GUI widget then update to device
    def Override(self, value):
        self.stringVar.set(value)
        self.Update()

################################################################################
#                                                                              #
#                                 cWinMain                                     #
#                                                                              #
################################################################################

## Class container for the main window and all of its elements
class cWinMain(tk.Tk):

    def __init__(self, SPI, ready, trigger, intValidate):
        super().__init__()

        self.SPI        = SPI
        self.ready      = ready
        self.trigger    = trigger

        self.next_cb = None
        self.acquireActive = False
        self.lastSpectrum = None
        self.dark = None
        self.clear()

        self.wavelengths = None
        self.wavenumbers = None
        self.eeprom = None
        self.pixels = args.pixels       # may be overridden by EEPROM

        self.colors = ["red", "blue", "cyan", "magenta", "yellow", "orange", "indigo", "violet", "white"]

        self.title(f"SPI SIG Version {VERSION}")

        cCfgString.SPI  = self.SPI
        cCfgEntry.SPI   = self.SPI
        cCfgEntry.ready = self.ready

        self.cbIntValidate = self.register(intValidate)
        cCfgEntry.validate = self.cbIntValidate

        # configuration frame on the left
        self.configFrame = tk.Frame(self)
        self.configFrame.grid(row=0, column=0, sticky="n")

        cCfgString.frame = self.configFrame
        cCfgEntry.frame  = self.configFrame

        # main graph frame on the right
        self.drawFrame = tk.Frame(self)

        self.figure = Figure(dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.drawFrame)
        self.graph = self.figure.add_subplot()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.drawFrame.grid(row=0, column=1, sticky="news")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # add the toolbar below
        self.toolbarFrame = tk.Frame(self)
        self.toolbarFrame.grid(row=1,column=1)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbarFrame)

        # populate all the controls within the Configuration frame
        self.initConfigFrame()

        # doing this BEFORE initial FPGA initialization, because if you do it
        # AFTER, you'll need to re-run FPGAInit() to reset set all the
        # acquisition parameters
        if args.eeprom_file:
            self.eeprom = EEPROM(pathname=args.eeprom_file)
        elif args.eeprom:
            self.eeprom = EEPROM(spi=self.SPI)

        if self.eeprom and args.excitation_nm < 0:
            args.excitation_nm = self.eeprom.excitation_nm_float

        self.generate_wavecal()

        debug("writing initial values to FPGA")
        self.FPGAInit()

        self.stop() if args.paused else self.start()

        if args.test:
            self.after(1000, self.test)

        self.mainloop()

        debug("exiting")

    ## The "Configuration" frame contains all the left-hand controls
    def initConfigFrame(self):

        buttonRow = 0
        def rows() -> int:
            return len(self.configObjects) + buttonRow

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

        # MZ: for Level Trigger, read uint16 CONFIG_REGISTER (0x12), set bit 7 high (|= 0x80), then write (0x92) 

        # Empty list for the config objects # Name              row     value                       address
        self.configObjects = []             # ----------------- ------- --------------------------- -------
        # Create an object for the FPGA Revision (special case, we want this box read only)
        self.configObjects.append(cCfgString("FPGA Revision"   , rows(), "00.0.00"                 , 0x10, read_len=8))
        self.configObjects[rows()-1].entry.config(state='disabled', disabledbackground='light grey', disabledforeground='black')
        self.configObjects.append(cCfgEntry("Integration Time" , rows(), args.integration_time_ms  , 0x11, write_len=4, read_len=4)) # note value is 24-bit
        self.configObjects.append(cCfgEntry("Detector Gain"    , rows(), args.gain_db              , 0x14))
        self.configObjects.append(cCfgEntry("Start Line 0"     , rows(), args.start_line           , 0x50))
        self.configObjects.append(cCfgEntry("Stop Line 0"      , rows(), args.stop_line            , 0x51))

        # store a key-value dict for name-based lookups
        self.configMap = {}
        for obj in self.configObjects:
            self.configMap[obj.name] = obj

        buttonRow += 1

        # [Update] [Start/Stop]
        self.btnUpdate = tk.Button(self.configFrame, text='Update', command=self.FPGAUpdate)
        self.btnUpdate.grid(row=rows(), column=0)
        self.textStart = tk.StringVar()
        self.textStart.set("???")
        self.btnStart = tk.Button(self.configFrame, textvariable=self.textStart, command=self.toggleStart)
        self.btnStart.grid(row=rows(), column=1)
        buttonRow += 1

        # [Save] [Clear]
        self.btnSave = tk.Button(self.configFrame, text="Save", command=self.save)
        self.btnSave.grid(row=rows(), column=0)
        self.btnClear = tk.Button(self.configFrame, text="Clear", command=self.clear)
        self.btnClear.grid(row=rows(), column=1)
        buttonRow += 1

        # [Batch] [Dark]
        self.btnBatch = tk.Button(self.configFrame, text="Batch", command=self.batch)
        self.btnBatch.grid(row=rows(), column=0)
        self.btnDark = tk.Button(self.configFrame, text="Dark", command=self.take_dark)
        self.btnDark.grid(row=rows(), column=1)
        buttonRow += 1

        # [Test] (hidden unless --paused)
        # if args.paused:
        #     self.btnTest = tk.Button(self.configFrame, text="Test", command=self.test)
        #     self.btnTest.grid(row=rows(), column=0, columnspan=2)
        #     buttonRow += 1

        # [note] 
        self.txtNote = tk.Text(self.configFrame, height=1, width=15)
        self.txtNote.grid(row=rows(), column=0, columnspan=2)
        buttonRow += 1

        # Resize the grid
        col_count, row_count = self.configFrame.grid_size()
        self.configFrame.grid_columnconfigure(0, minsize=120)
        self.configFrame.grid_columnconfigure(1, minsize=120)
        for row in range(row_count):
            self.configFrame.grid_rowconfigure(row, minsize=30)

    def start(self):
        with lock:
            debug("starting acquisition loop")
            self.textStart.set("Stop")
            self.acquireActive = True
            self.schedule_acquire(args.delay_ms)

    def stop(self):
        with lock:
            debug("pausing acquisition loop")
            self.textStart.set("Start")
            self.acquireActive = False

    def toggleStart(self):
        self.stop() if self.acquireActive else self.start()

    def generateBasename(self):
        ts = timestamp()
        integ = self.getValue("Integration Time")
        gain = self.getValue("Detector Gain")
        note = self.txtNote.get("1.0", "end-1c").strip()

        basename = ts
        if self.eeprom:
            basename += "-" + self.eeprom.serial_number

        basename += f"-{integ}ms-{gain}dB"
        if len(note) > 0:
            basename += f"-{note}"

        return basename

    def makeDataDir(self):
        try:
            os.mkdir(DATA_DIR)
        except:
            pass

    ##
    # @param to_disk: specify False if you only want the spectrum saved "on the
    #                 graph" (as a historical trace)
    def save(self, to_disk=True):
        if not args.save:
            return

        spectrum = self.lastSpectrum
        if spectrum is not None:
            basename = self.generateBasename()
            self.savedSpectra[basename] = spectrum

            if to_disk:
                x = self.getXAxis()
                self.makeDataDir()
                pathname = os.path.join(DATA_DIR, f"{basename}.csv")
                with open(pathname, "w") as outfile:
                    for i in range(len(spectrum)):
                        outfile.write(f"{x[i]:0.2f}, {spectrum[i]}\n")
                print(f"saved {pathname}")

    def take_dark(self):
        if self.dark is None:
            self.dark = self.lastSpectrum
        else:
            self.dark = None

    def clear(self):
        self.savedSpectra = {}

    def getValue(self, name) -> int:
        if name not in self.configMap:
            print(f"getValue: ERROR: unknown name {name}")
            return 0
        return self.configMap[name].value

    def apply2x2Binning(self, spectrum):
        binned = []
        for x in range(len(spectrum)-1):
            binned.append(round((spectrum[x] + spectrum[x+1]) / 2.0))
        binned.append(spectrum[-1])
        return binned

    def getSpectrum(self):
        with lock:

            ####################################################################
            # Trigger Acquisition
            ####################################################################

            if args.ext_trigger:
                debug("waiting on external trigger...")
                waitForDataReady(self.ready)
            else:
                # send trigger via the FT232H
                self.trigger.value = True
                waitForDataReady(self.ready)
                self.trigger.value = False

            ####################################################################
            # Read the spectrum (MZ: big-endian, seriously?)
            ####################################################################

            spectrum = []
            bytes_remaining = self.pixels * 2

            debug(f"getSpectrum: reading spectrum of {self.pixels} pixels")
            raw = []
            while self.ready.value:
                if bytes_remaining > 0:
                    bytes_this_read = min(args.block_size, bytes_remaining)

                    debug(f"getSpectrum: reading block of {bytes_this_read} bytes")
                    buf = bytearray(bytes_this_read)

                    # there is latency associated with this call, so call it as
                    # few times as possible (with the largest possible block size)
                    self.SPI.readinto(buf)

                    debug(f"getSpectrum: read block of {len(buf)} bytes")
                    raw.extend(list(buf))

                    bytes_remaining -= len(buf)

        ########################################################################
        # post-process spectrum
        ########################################################################

        # demarshall big-endian
        for i in range(0, len(raw)-1, 2):
            spectrum.append((raw[i] << 8) | raw[i+1])
        debug(f"getSpectrum: {len(spectrum)} pixels read")

        return spectrum

    def getXAxis(self):
        if self.wavenumbers is not None:
            return self.wavenumbers
        elif self.wavelengths is not None:
            return self.wavelengths
        else:
            return range(len(self.pixels))

    ## @todo probably faster if we used set_ydata()
    def graphSpectrum(self, y, label="live"):
        x = self.getXAxis()
        self.graph.plot(x, y, linewidth=0.5, label=label, marker='.')
        self.update_axes()
        self.graph.legend()

        self.canvas.draw()

    def initGraph(self):
        self.graph.clear()
        i = 0
        for label in sorted(self.savedSpectra):
            spectrum = self.savedSpectra[label]
            self.graphSpectrum(spectrum, label=label)

    def Acquire(self, graph=True, batch=False):
        # get the new spectrum
        debug("calling getSpectrum")
        spectrum = self.getSpectrum()
        debug("back from getSpectrum")
        if spectrum is None:
            debug("spectrum was None")
            return

        # post-process
        spectrum = self.apply2x2Binning(spectrum)
        if self.dark is not None:
            spectrum = [ spectrum[x] - self.dark[x] for x in range(min(len(self.dark), len(spectrum))) ]

        # record
        self.lastSpectrum = spectrum
        self.pixels = len(spectrum)
        debug(f"read {self.pixels} pixels")

        # graph
        if graph and not batch:
            debug(f"graphing spectrum: y {spectrum[:5]}, x {self.wavelengths[:5]}")
            self.initGraph()
            self.graphSpectrum(spectrum)

        # schedule next tick
        if self.acquireActive and not batch:
            self.schedule_acquire(args.delay_ms + self.getValue("Integration Time"))

        # for test()
        return spectrum

    def schedule_acquire(self, ms):
        debug(f"scheduling next tick in {ms}ms")
        if self.next_cb is not None:
            self.after_cancel(self.next_cb)
        self.next_cb = self.after(ms, self.Acquire)

    def FPGAInit(self):
        debug("performing FPGA Init")
        with lock:
            flushInputBuffer(self.ready, self.SPI) # get rid of any garbage on the line

        # Fetch the revision from the FPGA
        self.configObjects[0].SPIRead()

        # Iterate through each of the config objects and write to the FPGA
        for x in range(1, len(self.configObjects)):
            self.configObjects[x].SPIWrite()

        # initialize fixed acquisition parameters not currently exposed by the GUI
        for address, value, write_len, name in HARDCODED_PARAMETERS:
            send_command(SPI       = self.SPI,
                         ready     = self.ready,
                         address   = address,
                         value     = value,
                         write_len = write_len,
                         name      = name)

        self.take_throwaways()

    def take_throwaways(self):
        if args.throwaways > 0:
            debug("taking throwaways")
            for i in range(args.throwaways):
                self.Acquire()
                self.btnStart.update_idletasks()
            debug("done taking throwaways")

    def FPGAUpdate(self, force=False):
        debug("performing FPGA Update")
        with lock:
            flushInputBuffer(self.ready, self.SPI) # get rid of any garbage on the line

        # Iterate through each of the config objects and update to the FPGA if necessary
        changed = False
        for cfgObj in self.configObjects:
            if cfgObj.Update(force=force):
                changed = True

        # take throwaways if any acquisition parameters changed
        if changed:
            print(f"taking throwaways (pixels now {self.pixels})")
            self.take_throwaways()

    ############################################################################
    #                                                                          #
    #                           Batch Collection                               #
    #                                                                          #
    ############################################################################

    def batch(self):
        spectra = []
        labels = []
        for i in range(args.batch_count):
            label = f"meas-{i+1:02d}"
            debug(f"batch: collecting {label}")
            spectrum = self.Acquire(batch=True)
            spectra.append(spectrum)
            labels.append(label)

            delay_ms = args.delay_ms + self.getValue("Integration Time")
            sleep_ms(delay_ms)

        self.makeDataDir()

        filename = "batch-" + self.generateBasename() + ".csv"
        pathname = os.path.join(DATA_DIR, filename)

        with open(pathname, "w") as outfile:
            # metadata
            outfile.write(f"spi_console, {VERSION}\n")
            for key, value in self.configMap.items():
                outfile.write(f"cfg.{key}, {value.value}\n")
            for address, value, write_len, name in HARDCODED_PARAMETERS:
                outfile.write(f"fixed.{name}, {value}\n")
            for key, value in args.__dict__.items():
                outfile.write(f"args.{key}, {value}\n")
            if self.eeprom is not None:
                for key, value in self.eeprom.__dict__.items():
                    outfile.write(f"eeprom.{key}, {value}\n")
            outfile.write("\n")

            # header row
            outfile.write("pixel, wavelength")
            if self.wavenumbers is not None:
                outfile.write(", wavenumber")
            for label in labels:
                outfile.write(f", {label}")
            outfile.write("\n")

            # data
            for pixel in range(self.pixels):
                outfile.write(f"{pixel}, {self.wavelengths[pixel]:.2f}")
                if self.wavenumbers is not None:
                    outfile.write(f", {self.wavenumbers[pixel]:.2f}")
                for spectrum in spectra:
                    outfile.write(f", {spectrum[pixel]}")
                outfile.write("\n")
        print(f"saved {pathname}")

    ############################################################################
    #                                                                          #
    #                             Unit Testing                                 #
    #                                                                          #
    ############################################################################

    ##
    # @note This is a blocking callback run from a button event...not generally
    #       the most robust design.  If we want to grow this, we should spin-off
    #       a thread and flow-up graph updates via a dispatch to the GUI thread
    #       (or whatever the Tkinter equivalent would be).
    def test(self):
        if not args.paused:
            print("test() can only be started from a paused state")
            return

        ########################################################################
        # Data Collection
        ########################################################################

        self.test_start = datetime.datetime.now()
        self.min_elapsed_ms = 99999
        self.max_elapsed_ms = -1

        self.spectra = []
        self.headers = { 
            "label": [], 
            "elapsed_ms": [],
            "lo": [],
            "hi": [],
            "median": []
        }
        for i in range(args.test_count):
            debug(f"starting test measurement {i+1:3d}/{args.test_count}")
            time_start = datetime.datetime.now()

            debug("calling acquire")
            spectrum = self.Acquire(graph=False)
            debug("back from acquire")

            elapsed_ms = (datetime.datetime.now() - time_start).total_seconds() * 1000.0
            self.min_elapsed_ms = min(elapsed_ms, self.min_elapsed_ms)
            self.max_elapsed_ms = max(elapsed_ms, self.max_elapsed_ms)

            print(f"collected {i+1:3d}/{args.test_count} ({elapsed_ms:.2f}ms)")

            med = median(spectrum)
            hi = max(spectrum)
            lo = min(spectrum)

            self.spectra.append(spectrum)
            self.headers["label"].append(f"meas-{i+1:02d}")
            self.headers["elapsed_ms"].append(elapsed_ms)
            self.headers["median"].append(med)
            self.headers["lo"].append(lo)
            self.headers["hi"].append(hi)

            sleep_ms(args.delay_ms)

        self.test_stop = datetime.datetime.now()

        ########################################################################
        # Metrics
        ########################################################################

        self.elapsed_ms = (self.test_stop - self.test_start).total_seconds() * 1000.0
        self.avg_measurement_period_ms = self.elapsed_ms / args.test_count
        self.scan_rate = 1000.0 / self.avg_measurement_period_ms

        print("=" * 50)
        print(f"Settings:        {args.baud_mhz} MHz with block size {args.block_size} bytes")
        print(f"Total Elapsed:   {self.elapsed_ms:.2f} ms for {args.test_count} measurements")
        print(f"Avg Meas Period: {self.avg_measurement_period_ms:.2f} ms per measurement (min {self.min_elapsed_ms:.2f}, max {self.max_elapsed_ms:.2f})")
        print(f"Avg Scan Rate:   {self.scan_rate:.2f} measurements/sec")
        print("=" * 50)

        ########################################################################
        # Linearity Ramp (optional)
        ########################################################################

        if args.test_linearity:
            for ms in range(args.test_ramp_start, args.test_ramp_stop + 1, args.test_ramp_incr):
                print(f"collecting ramp measurement at {ms}ms")
                self.configMap["Integration Time"].Override(ms)
                self.take_throwaways()

                time_start = datetime.datetime.now()
                spectrum = self.Acquire()
                elapsed_ms = (datetime.datetime.now() - time_start).total_seconds() * 1000.0
                self.btnClear.update_idletasks()

                self.spectra.append(spectrum)
                self.headers["label"].append(f"ramp-{ms}ms")
                self.headers["elapsed_ms"].append(elapsed_ms)

                self.save(to_disk=False)
                self.btnClear.update_idletasks()
                sleep_ms(args.delay_ms)

        ########################################################################
        # Done
        ########################################################################

        self.save_report()
        self.quit()

    def save_report(self):
        self.makeDataDir()
        if self.eeprom is not None:
            filename = f"test-{timestamp()}-{self.eeprom.serial_number}.csv"
        else:
            filename = f"test-{timestamp()}.csv"
        pathname = os.path.join(DATA_DIR, filename)

        with open(pathname, "w") as outfile:
            # metadata
            outfile.write(f"spi_console, {VERSION}\n")
            for key, value in self.configMap.items():
                outfile.write(f"cfg.{key}, {value.value}\n")
            for address, value, write_len, name in HARDCODED_PARAMETERS:
                outfile.write(f"fixed.{name}, {value}\n")
            for key, value in args.__dict__.items():
                outfile.write(f"args.{key}, {value}\n")
            if self.eeprom is not None:
                for key, value in self.eeprom.__dict__.items():
                    outfile.write(f"eeprom.{key}, {value}\n")
            for key in ['test_start', 'test_stop', 'elapsed_ms', 'min_elapsed_ms', 'max_elapsed_ms', 'avg_measurement_period_ms', 'scan_rate']:
                outfile.write(f"metrics.{key}, {getattr(self, key)}\n")
            outfile.write("\n")

            # extra header rows
            for key in self.headers:
                if key != "label":
                    outfile.write(f", {key}")
                    if self.wavenumbers is not None:
                        outfile.write(",")
                    for value in self.headers[key]:
                        outfile.write(f", {value:.2f}")
                    outfile.write("\n")

            # label header row
            outfile.write("pixel, wavelength")
            if self.wavenumbers is not None:
                outfile.write(", wavenumber")
            for label in self.headers["label"]:
                outfile.write(f", {label}")
            outfile.write("\n")

            # data
            for pixel in range(self.pixels):
                outfile.write(f"{pixel}, {self.wavelengths[pixel]:.2f}")
                if self.wavenumbers is not None:
                    outfile.write(f", {self.wavenumbers[pixel]:.2f}")
                for spectrum in self.spectra:
                    outfile.write(f", {spectrum[pixel]}")
                outfile.write("\n")
        print(f"saved {pathname}")

    def generate_wavecal(self):
        if self.eeprom is not None:
            self.pixels = self.eeprom.active_pixels_horizontal
            coeffs = self.eeprom.wavelength_coeffs
            if math.isnan(coeffs[4]):
                coeffs[4] = 0
        else:
            coeffs = [0, 1, 0, 0, 0]

        self.wavelengths = []
        for i in range(self.pixels):
            wavelength = coeffs[0]               \
                       + coeffs[1] * i           \
                       + coeffs[2] * i * i       \
                       + coeffs[3] * i * i * i   \
                       + coeffs[4] * i * i * i * i
            self.wavelengths.append(wavelength)
        debug(f"wavelengths = ({self.wavelengths[0]:.2f}, {self.wavelengths[-1]:.2f})")

        if args.excitation_nm > 0:
            self.wavenumbers = []
            base = 1e7 / args.excitation_nm
            for i in range(self.pixels):
                wavenumber = 0
                if self.wavelengths[i] != 0:
                    wavenumber = base - 1e7 / self.wavelengths[i]
                self.wavenumbers.append(wavenumber)
            debug(f"wavenumbers = ({self.wavenumbers[0]:.2f}, {self.wavenumbers[-1]:.2f})")

    def update_axes(self):
        if not args.eeprom:
            xlabel = "pixel"
        elif self.wavenumbers is not None:
            xlabel = "wavenumber (cm⁻¹)"
        elif self.wavelengths is not None:
            xlabel = "wavelength (nm)"
        else:
            xlabel = "whut"
        self.figure.get_axes()[0].set_xlabel(xlabel)

################################################################################
#                                                                              #
#                                  EEPROM                                      #
#                                                                              #
################################################################################

class EEPROM:

    def __init__(self, spi=None, pathname=None):
        self.spi = spi
        self.pathname = pathname

        self.buffers = []

        if spi:
            self.read_spi()
            self.parse_buffers()
        elif pathname:
            self.read_json()

    def read_spi(self):
        for page in range(5):
            buf = self.read_page(page)
            self.buffers.append(buf)

    def read_page(self, page) -> list:
        with lock:
            # send 0xb0 command to tell FPGA to load EEPROM page into FPGA buffer
            unbuffered_cmd = fixCRC([START, 0, 2, 0xB0, 0x40 + page, CRC, END])
            buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + 1)
            buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
            self.spi.write_readinto(buffered_cmd, buffered_response)
            print(f">> EEPROMRead: {toHex(buffered_cmd)} -> {toHex(buffered_response)}")

            # MZ: API says "wait for SPEC_BUSY to be deasserted...why aren't we doing that?
            sleep_ms(10) # empirically determined 10ms delay

            # send 0x31 command to read the buffered page from the FPGA
            unbuffered_cmd = fixCRC([START, 0, 65, 0x31, CRC, END])
            buffered_response = bytearray(len(unbuffered_cmd) + READ_RESPONSE_OVERHEAD + 64) # MZ: including kludged -1
            buffered_cmd = buffer_bytearray(unbuffered_cmd, len(buffered_response))
            self.spi.write_readinto(buffered_cmd, buffered_response)

        buf = decode_read_response(unbuffered_cmd, buffered_response, "read_eeprom_page", missing_echo_len=1)
        debug(f"decoded {len(buf)} values from EEPROM")
        return buf

    def parse_buffers(self):
        self.format = self.unpack((0, 63,  1), "B", "format")
        debug(f"parsing EEPROM format {self.format}")

       #self.model                           = self.unpack((0,  0, 16), "s", "model")
        self.serial_number                   = self.unpack((0, 16, 16), "s", "serial")

        self.wavelength_coeffs = []
        self.wavelength_coeffs.append(self.unpack((1,  0,  4), "f", "wavecal_coeff_0"))
        self.wavelength_coeffs.append(self.unpack((1,  4,  4), "f"))
        self.wavelength_coeffs.append(self.unpack((1,  8,  4), "f"))
        self.wavelength_coeffs.append(self.unpack((1, 12,  4), "f"))
        self.wavelength_coeffs.append(self.unpack((2, 21,  4), "f", "wavecal_coeff_4") if self.format > 7 else 0)
        debug(f"loaded wavecal: {self.wavelength_coeffs}")

        self.active_pixels_horizontal        = self.unpack((2, 16,  2), "H", "pixels")
       #self.active_pixels_vertical          = self.unpack((2, 19,  2), "H" if self.format >= 4 else "h")
       #self.actual_horizontal               = self.unpack((2, 25,  2), "H" if self.format >= 4 else "h", "actual_horiz")
       #self.roi_horizontal_start            = self.unpack((2, 27,  2), "H" if self.format >= 4 else "h")
       #self.roi_horizontal_end              = self.unpack((2, 29,  2), "H" if self.format >= 4 else "h")
       #self.roi_vertical_region_1_start     = self.unpack((2, 31,  2), "H" if self.format >= 4 else "h")
       #self.roi_vertical_region_1_end       = self.unpack((2, 33,  2), "H" if self.format >= 4 else "h")

        self.excitation_nm_float             = self.unpack((3, 36,  4), "f", "excitation(float)")

        debug(f"ACTIVE pixels horizontal: {self.active_pixels_horizontal}")
        debug(f"         excitation (nm): {self.excitation_nm_float}")
       #debug(f"  active pixels vertical: {self.active_pixels_vertical}")
       #debug(f"          horizontal ROI: ({self.roi_horizontal_start}, {self.roi_horizontal_end})")
       #debug(f"            vertical ROI: ({self.roi_vertical_region_1_start}, {self.roi_vertical_region_1_end})")

    def read_json(self):
        with open(self.pathname) as f:
            data = json.load(f)
            debug(f"loaded JSON from {self.pathname}: {data}")

            self.serial_number              = data.get("serial_number")
            self.active_pixels_horizontal   = int(data.get("active_pixels_horizontal", args.pixels))
            self.excitation_nm_float        = float(data.get("excitation_nm_float", 0))

            if "wavelength_coeffs" in data:
                self.wavelength_coeffs = [float(x) for x in data["wavelength_coeffs"]]

    ##
    # Unpack a single field at a given buffer offset of the given datatype.
    #
    # @param address    a tuple of the form (buf, offset, len)
    # @param data_type  see https://docs.python.org/2/library/struct.html#format-characters
    # @param label      for debug output
    def unpack(self, address, data_type, label=None):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        if page > len(self.buffers):
            print(f"invalid EEPROM page {page}")
            return

        buf = self.buffers[page]
        if buf is None or end_byte > len(buf):
            print(f"error unpacking EEPROM page {page}, offset {start_byte}, len {length} as {data_type}: buf {buf} ({label})")
            return

        if data_type == "s":
            unpack_result = ""
            for c in buf[start_byte:end_byte]:
                if c == 0:
                    break
                unpack_result += chr(c)
        else:
            unpack_result = 0
            try:
                unpack_result = struct.unpack(data_type, buf[start_byte:end_byte])[0]
            except:
                print(f"error unpacking EEPROM page {page}, offset {start_byte}, len {length} as {data_type} ({label})")

        if label is None:
            debug("Unpacked [%s]: %s" % (data_type, unpack_result))
        else:
            debug("Unpacked [%s]: %s (%s)" % (data_type, unpack_result, label))
        return unpack_result

################################################################################
#                                                                              #
#                                   main()                                     #
#                                                                              #
################################################################################

# parse command-line args (user may need different trigger/ready pins)
args = parseArgs(sys.argv)
if not runnable:
    sys.exit(1)

# Initialize the SPI bus on the FT232H
SPI = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# Initialize READY (input)
ready = digitalio.DigitalInOut(getattr(board, args.ready_pin.upper()))
ready.direction = digitalio.Direction.INPUT

# Initialize TRIGGER (output)
trigger = digitalio.DigitalInOut(getattr(board, args.trigger_pin.upper()))
trigger.direction = digitalio.Direction.OUTPUT
trigger.value = False

# Take control of the SPI Bus
while not SPI.try_lock():
    pass

# Configure the SPI bus
SPI.configure(baudrate=args.baud_mhz * 1e6, phase=0, polarity=0, bits=8)

# Create the main window and pass in the handles
winSIG = cWinMain(SPI, ready, trigger, fIntValidate)
