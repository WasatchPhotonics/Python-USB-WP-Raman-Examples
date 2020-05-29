#!/usr/bin/env python -u
################################################################################
#                             MonteCarloTest.py                                #
################################################################################
#                                                                              #
#  DESCRIPTION:  A load-test script to hammer Wasatch spectrometers with a     #
#                variety of random commands to thoroughly wring-out the API.   #
#                                                                              #
################################################################################

import sys
import random
import usb.core
import argparse
import datetime
import traceback
from time import sleep

################################################################################
# globals
################################################################################

VID = 0x24aa
HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0

################################################################################
#                                                                              #
#                                 APICommand                                   #
#                                                                              #
################################################################################

class APICommand(object):
    
    def __init__(self, 
            name, 
            getter=None,                   # opcode
            setter=None,                   # opcode
            dataType=None,                 # "Bool", "Uint32" etc
            readLen=None,                  # useful bytes to read from getter
            readBack=None,                 # full bytes to read from getter
            setRange=None,                 # range of setter values
            setterDisabled=False,          # skip the setter when testing
            getterDisabled=False,          # skip the getter when testing
            supports=None,                 # set of supported architectures ("ARM", "FX2" etc)
            wValue=None,                   # explicit wValue code, if any 
            wIndexRange=None,              # range of possible wIndex values
            enum=None,                     # set of zero-indexed strings for supported integral values
            getFakeBufferLen=None,         # pass a fake "write buffer" of this length even on reads
            setFakeBufferFromValue=False,  # generate a fake "write buffer" of 'value' bytes
            setFakeLenFromValue=False,     # pass wValue as wLength
            getLittleEndian=False,         # some commands return value in little endian; all are believed to set big-endian
            setDelayMS=0,                  # delay after setting value before attempting read
            requiresLaserModEnabled=False, # can't be used unless laser modulation is enabled
            usesLaser=False,               # command involves the laser
            notes=None):                   # comments                                    (not used)

        self.name                       = name        
        self.getter                     = getter
        self.setter                     = setter
        self.dataType                   = dataType
        self.readLen                    = readLen
        self.readBack                   = readBack
        self.setRange                   = setRange
        self.setterDisabled             = setterDisabled
        self.getterDisabled             = getterDisabled
        self.supports                   = supports
        self.wValue                     = wValue
        self.wIndexRange                = wIndexRange
        self.enum                       = enum
        self.getFakeBufferLen           = getFakeBufferLen
        self.setFakeBufferFromValue     = setFakeBufferFromValue
        self.setFakeLenFromValue        = setFakeLenFromValue
        self.getLittleEndian            = getLittleEndian
        self.setDelayMS                 = setDelayMS
        self.requiresLaserModEnabled    = requiresLaserModEnabled
        self.usesLaser                  = usesLaser
        self.notes                      = notes

    def __str__(self):
        return self.name

    def getterName(self):
        return "GET_" + self.name

    def setterName(self):
        return "SET_" + self.name

    def isSupported(self, pid):
        if self.supports is None:
            return True
        elif "FX2" in self.supports and pid in (0x1000, 0x2000):
            return True
        elif "ARM" in self.supports and pid == 0x4000:
            return True
        elif "InGaAs" in self.supports and pid == 0x2000:
            return True
        else:
            return False

    def makeRandomValue(self):
        if self.setRange:
            value = random.randrange(self.setRange[0], self.setRange[1] + 1)
            display = "0x%x (%d)" % (value, value)
            return (value, display)

        bits = None
        dt = self.dataType.upper()
        if dt == "BOOL":
            bits = 1
        elif dt == "UINT8":
            bits = 8
        elif dt == "UINT12":
            bits = 12
        elif dt == "UINT16":
            bits = 16
        elif dt == "UINT24":
            bits = 24
        elif dt == "UINT32":
            bits = 32
        elif dt == "UINT40":
            bits = 40

        if bits:
            value = random.randrange(2**bits)
            display = "0x%x (%d)" % (value, value)
            return (value, display)

        if dt == "FLOAT16":
            msb = random.randrange(3)   # technically 256, but only used for gain so...
            lsb = random.randrange(256)
            value = (msb << 8) | lsb    # we always set in big-endian
            display = "0x%04x (%s)" % (value, (msb + float(lsb)/256.0))
            return (value, display)

        if dt == "ENUM" and self.enum:
            value = random.randrange(len(self.enum))
            display = "%d (%s)" % (value, self.enum[value])
            return (value, display)

        # no current need to support Byte[], Void or String
        return None

    def parseResult(self, result):
        raw = 0
        display = None

        if not result or len(result) == 0:
            raise Exception("%s returned nothing" % self.name)

        # trim extra readBack bytes from integration time, etc
        if len(result) > self.readLen:
            result = result[:self.readLen]

        # after this, we treat all responses like they're big-endian
        if self.getLittleEndian:
            result = list(reversed(result))

        dt = self.dataType.upper()
        if dt == "BOOL":
            raw = result[0] != 0
        elif dt == "BYTE[]":
            raw = result
        elif dt == "ENUM":
            raw = result[0]
            if self.enum is not None and raw < len(self.enum):
                display = self.enum[raw]
            else:
                display = "ERROR"
        elif dt == "FLOAT16":
            if len(result) < 2:
                raise Exception("insufficient data") 
            msb = result[0] 
            lsb = result[1]
            raw = (msb << 8) | lsb
            display = str(float(msb) + float(lsb) / 256.0)
        elif dt == "STRING":
            raw = result
            display = ""
            for c in result:
                if c == 0:
                    break
                elif 31 < c < 127:
                    display += chr(c)
                else:
                    display += "."
        elif dt == "VOID":
            pass
        elif dt == "UINT8":
            raw = result[0]
        elif dt == "UINT12":
            if len(result) < 2:
                raise Exception("insufficient data") 
            raw = ((result[0] << 8) | result[1]) & 0xfff
        elif dt == "UINT16":
            if len(result) < 2:
                raise Exception("insufficient data") 
            raw = (result[0] << 8) | result[1]
        elif dt == "UINT24":
            if len(result) < 3:
                raise Exception("insufficient data") 
            raw = (result[0] << 16) | (result[1] << 8) | result[2]
        elif dt == "UINT32":
            if len(result) < 4:
                raise Exception("insufficient data") 
            raw = (result[0] << 24) | (result[1] << 16) | (result[2] << 8) | result[3]
        elif dt == "UINT40":
            if len(result) < 5:
                raise Exception("insufficient data") 
            raw = (result[0] << 32) | (result[1] << 24) | (result[2] << 16) | (result[3] << 8) | result[4]
        else:
            display = "Unknown datatype: %s" % dt
            
        if display is None:
            display = str(raw)

        if dt in ("BYTE[]", "STRING"):
            rawDisplay = str(raw)
        else:
            rawDisplay = "0x%x" % raw

        return (raw, rawDisplay, display)

    def buildPayload(self, value):
        wValue = 0
        wIndex = 0
        buf = [0] * 8

        dt = self.dataType.upper()
        if dt == "BOOL":
            wValue = 1 if value else 0
        elif dt == "ENUM":
            wvalue = value
        elif dt == "FLOAT16":
            wValue = value
        elif dt == "VOID":
            pass
        elif dt == "UINT8":
            wValue = value & 0xff
        elif dt == "UINT12":
            wValue = value & 0xfff
        elif dt == "UINT16":
            wValue = value & 0xffff
        elif dt == "UINT24":
            wValue = value & 0xffff
            wIndex = (value >> 16) & 0xff
        elif dt == "UINT32":
            wValue = value & 0xffff
            wIndex = (value >> 16) & 0xffff
        elif dt == "UINT40":
            wValue = value & 0xffff
            wIndex = (value >> 16) & 0xffff
            buf[0] = (value >> 32) & 0xff
        else:
            raise Exception("buildPayload(%s): not currently supporting writing type %s" % (self.name, self.dataType))

        if self.setFakeBufferFromValue:
            buf = [0] * int(value)

        if self.setFakeLenFromValue:
            buf = int(value)

        return (wValue, wIndex, buf)

################################################################################
#                                                                              #
#                                 TestFixture                                  #
#                                                                              #
################################################################################

class TestFixture(object):

    def __init__(self):
        self.timeStart = datetime.datetime.now()
        self.last_usb_timestamp = None

        self.cmds = {}
        self.lastValues = {}

        #self.simpleCommands = ('INTEGRATION_TIME', 'CCD_OFFSET', 'CCD_GAIN', 'CCD_TEC_ENABLE') #Hecox: original
        self.simpleCommands = ('INTEGRATION_TIME') #Hecox: only run integration time in simple mode for now
        
        self.processArgs()
        self.loadCommands()
        self.resetCounts()

    def resetCounts(self):
        self.errorCount = 0
        self.skipCount = 0
        self.commandCount = 0
        self.simpleIndex = 0

    def complete(self):
        return self.max is not None and self.commandCount >= self.max

    def duration(self):
        now = datetime.datetime.now()
        delta = datetime.datetime.now() - self.timeStart
        return delta.total_seconds()

    def throttle_usb(self):
        if self.delay_ms > 0:
            if self.last_usb_timestamp is not None:
                next_usb_timestamp = self.last_usb_timestamp + datetime.timedelta(milliseconds=self.delay_ms)
                if datetime.datetime.now() < next_usb_timestamp:
                    while datetime.datetime.now() < next_usb_timestamp:
                        sleep(0.001) 
            self.last_usb_timestamp = datetime.datetime.now()

    def addCommand(self, cmd):
        self.cmds[cmd.name] = cmd

    def loadCommands(self):
        self.addCommand(APICommand("ACTUAL_FRAMES",                getter=0xE4,              dataType="Uint16",  readLen=2))
        self.addCommand(APICommand("ACTUAL_INTEGRATION_TIME",      getter=0xDF,              dataType="Uint24",  readLen=3, readBack=6, getLittleEndian=True, notes="Response of 0xffffff indicates error"))
        self.addCommand(APICommand("CCD_GAIN",                     getter=0xC5, setter=0xB7, dataType="Float16", readLen=2, getLittleEndian=True, notes="Returns/Takes odd 16-bit half-precision float, where MSB is integral part and LSB is fractional"))
        self.addCommand(APICommand("CCD_OFFSET",                   getter=0xC4, setter=0xB6, dataType="Uint16",  readLen=2, setRange=(0, 3000), getLittleEndian=True, notes="guessing about little-endian"))
        self.addCommand(APICommand("CCD_SENSING_THRESHOLD",        getter=0xD1, setter=0xD0, dataType="Uint16",  readLen=2, setRange=(0, 5000), getLittleEndian=True))
        self.addCommand(APICommand("CCD_TEC_ENABLE",               getter=0xDA, setter=0xD6, dataType="Bool",    readLen=1)) 
        self.addCommand(APICommand("CCD_TEMP",                     getter=0xD7,              dataType="Uint16",  readLen=2, notes="Raw 12-bit ADC output from the TEC"))
        self.addCommand(APICommand("CCD_TEMP_SETPOINT",            getter=0xD9, setter=0xD8, dataType="Uint16",  readLen=2, setterDisabled=True, notes="Send raw 12-bit DAC value to TEC; normally computed from user input in DegC, converted to raw using degCToDACCoeffs from EEPROM; degC should not exceed min/max values from EEPROM; disabled in test because dangerous"))
        self.addCommand(APICommand("CCD_THRESHOLD_SENSING_MODE",   getter=0xCF, setter=0xCE, dataType="Bool",    readLen=1))
        self.addCommand(APICommand("CCD_TRIGGER_SOURCE",           getter=0xD3, setter=0xD2, dataType="Enum",    readLen=1, setterDisabled=True, enum=("USB", "EXTERNAL"), notes="disabled in test because assuming would freeze spectrometer?"))
        self.addCommand(APICommand("CF_SELECT",                    getter=0xEC, setter=0xEB, dataType="Bool",    readLen=1, supports=("InGaAs"), notes="AKA, HIGH_GAIN_MODE_ENABLED"))
        self.addCommand(APICommand("CODE_REVISION",                getter=0xC0,              dataType="Byte[]",  readLen=4, getLittleEndian=True, notes="Bytes are read-out backwards ([0xaa bb cc dd] means version dd.cc.bb.aa)"))
        self.addCommand(APICommand("COMPILATION_OPTIONS",          getter=0xFF,              dataType="Uint16",  readLen=2, wValue=0x04, getLittleEndian=True, getFakeBufferLen=8))
        self.addCommand(APICommand("DFU_MODE",                                  setter=0xFE, dataType="Void",               setterDisabled=True, supports=('ARM'), notes="Used to prepare STM32 ARM to accept firmware update via DfuSe Demonstrator (en.stsw-stm32080); takes no arguments; disabled in test because bad idea"))
        self.addCommand(APICommand("EXTERNAL_TRIGGER_OUTPUT",      getter=0xE1, setter=0xE0, dataType="Enum",    readLen=1, usesLaser=True, setterDisabled=True, enum=("LASER_MODULATION", "INTEGRATION_ACTIVE_PULSE")))
        self.addCommand(APICommand("FPGA_REV",                     getter=0xB4,              dataType="String",  readLen=7))
        self.addCommand(APICommand("HORIZ_BINNING",                getter=0xBC, setter=0xB8, dataType="Enum",    readLen=1, setterDisabled=True, enum=("NONE", "TWO_PIXEL", "FOUR_PIXEL"), supports=("ARM"), notes="MZ: couldn't get this to work on ARM"))
        self.addCommand(APICommand("INTEGRATION_TIME",             getter=0xBF, setter=0xB2, dataType="Uint24",  readLen=3, getLittleEndian=True, setRange=(10, 1000), readBack=6, notes="Integration time in ms or 10ms (see OPT_INT_TIME_RES) sent as 32-bit word: LSW as wValue, MSW as wIndex (big-endian within each)"))
        self.addCommand(APICommand("INTERLOCK",                    getter=0xEF,              dataType="Bool",    readLen=1, supports=("FX2"), notes="Couldn't get to work on ARM, checking with Jason"))
        self.addCommand(APICommand("LASER_ENABLED",                getter=0xE2, setter=0xBE, dataType="Bool",    readLen=1, usesLaser=True, setterDisabled=True, notes="disabled in test because dangerous"))
        #self.addCommand(APICommand("LASER_MOD_ENABLED",            getter=0xE3, setter=0xBD, dataType="Bool",    readLen=1, usesLaser=True, getFakeBufferLen=8))
        #self.addCommand(APICommand("LASER_MOD_DURATION",           getter=0xC3, setter=0xB9, dataType="Uint40",  readLen=5, usesLaser=True, requiresLaserModEnabled=True, setterDisabled=True, getLittleEndian=True, notes="Never used in ENLIGHTEN? In microsec; disabled in test because doesn't seem to work"))
        #self.addCommand(APICommand("LASER_MOD_PERIOD",             getter=0xCB, setter=0xC7, dataType="Uint40",  readLen=5, usesLaser=True, getterDisabled=True, requiresLaserModEnabled=True, setRange=(100, 100), setFakeLenFromValue=True, notes="API Kludge: sending integral percentage as length of fake buffer"))
        #self.addCommand(APICommand("LASER_MOD_PULSE_DELAY",        getter=0xCA, setter=0xC6, dataType="Uint40",  readLen=5, usesLaser=True, setRange=(0, 5000), getLittleEndian=True, requiresLaserModEnabled=True))
        #self.addCommand(APICommand("LASER_MOD_PULSE_WIDTH",        getter=0xDC, setter=0xDB, dataType="Uint40",  readLen=5, usesLaser=True, getterDisabled=True, requiresLaserModEnabled=True, setDelayMS=100, getLittleEndian=True, setRange=(1, 100), setFakeBufferFromValue=True, notes="getter disabled because doesn't seem to work"))
        #self.addCommand(APICommand("LASER_RAMPING_MODE",           getter=0xEA, setter=0xE9, dataType="Bool",    readLen=1, usesLaser=True, supports=("ARM")))
        #self.addCommand(APICommand("LASER_TEMP",                   getter=0xD5,              dataType="Uint16",  readLen=2, usesLaser=True, getLittleEndian=True, notes="causes problems on ARM if no laser connected?"))
        #self.addCommand(APICommand("LASER_TEMP_SETPOINT",          getter=0xE8, setter=0xE7, dataType="Uint12",  readLen=1, usesLaser=True, getterDisabled=True, getFakeBufferLen=8, setRange=(63, 127), supports=("ARM"), notes="TODO: Unclear what this returns; documented length of 1 byte is insufficient for 12-bit DAC? getter disabled in testing because wasn't working"))
        self.addCommand(APICommand("LINE_LENGTH",                  getter=0xFF,              dataType="Uint16",  readLen=2, getLittleEndian=True, wValue=0x03, notes="causes problems on ARM in combination with others?"))
        #self.addCommand(APICommand("LINK_LASER_MOD_TO_INTEG_TIME", getter=0xDE, setter=0xDD, dataType="Bool",    readLen=1, usesLaser=True)) 
        self.addCommand(APICommand("MODEL_CONFIG",                 getter=0xFF, setter=0xA2, dataType="Byte[]",  readLen=64, wValue=0x01, wIndexRange=(0, 5), setterDisabled=True, notes="On read, pass desired page index (0-7) via wIndex; BatchTest; on write, wValue should be 0x3c00 + 64 * (zero-indexed page index); buf should be 64 bytes; disabled in testing because very stupid"))
        self.addCommand(APICommand("OPT_ACT_INT_TIME",             getter=0xFF,              dataType="Bool",    readLen=1, wValue=0x0B, getFakeBufferLen=8))
        self.addCommand(APICommand("OPT_AREA_SCAN",                getter=0xFF,              dataType="Bool",    readLen=1, wValue=0x0A, getFakeBufferLen=8))
        self.addCommand(APICommand("OPT_CF_SELECT",                getter=0xFF,              dataType="Bool",    readLen=1, wValue=0x07, getFakeBufferLen=8))
        self.addCommand(APICommand("OPT_DATA_HDR_TAB",             getter=0xFF,              dataType="Enum",    readLen=1, wValue=0x06, enum=("NONE", "OCEAN_OPTICS", "WASATCH")))
        self.addCommand(APICommand("OPT_HORIZONTAL_BINNING",       getter=0xFF,              dataType="Bool",    readLen=1, wValue=0x0C, notes="Not sure how this is used"))
        self.addCommand(APICommand("OPT_INT_TIME_RES",             getter=0xFF,              dataType="Enum",    readLen=1, wValue=0x05, enum=("ONE_MS", "TEN_MS", "SWITCHABLE")))
        self.addCommand(APICommand("OPT_LASER",                    getter=0xFF,              dataType="Enum",    readLen=1, wValue=0x08, enum=("NONE", "INTERNAL", "EXTERNAL")))
        self.addCommand(APICommand("OPT_LASER_CONTROL",            getter=0xFF,              dataType="Enum",    readLen=1, wValue=0x09, enum=("MODULATION", "TRANSITION_POINTS", "RAMPING")))
        self.addCommand(APICommand("RESET_FPGA",                                setter=0xB5, dataType="Void",               setterDisabled=True, notes="disabled in test because bad idea"))
        self.addCommand(APICommand("SELECTED_LASER",               getter=0xEE, setter=0xED, dataType="Bool",    readLen=1))
        self.addCommand(APICommand("TRIGGER_DELAY",                getter=0xAB, setter=0xAA, dataType="Uint24",  readLen=3, getLittleEndian=True, setRange=(1, 6000000), supports=("ARM"), notes="Delay is in 0.5us, supports 24-bit unsigned value (about 8.3sec)"))
        #self.addCommand(APICommand("VR_CONTINUOUS_CCD",            getter=0xCC, setter=0xC8, dataType="Bool",    readLen=1, notes="When using external triggering, perform multiple acquisitions on a single inbound trigger event."))
        #self.addCommand(APICommand("VR_NUM_FRAMES",                getter=0xCD, setter=0xC9, dataType="Uint8",   readLen=1, notes="When using continuous CCD acquisitions with external triggering, how many spectra are being acquired per trigger event."))

    def enumerate(self):
        print("Using VID 0x%04x, PID 0x%04x and %d pixels (block size %d)" % (VID, self.pid, self.pixels, self.block_size))
        self.dev = usb.core.find(idVendor=VID, idProduct=fixture.pid)
        if self.dev is None:
            return False

        if fixture.debug:
            print(self.dev)

        return True

    def apiReport(self):
        print("The following test workarounds were found in the command listing:\n")
        print("setterDisabled:         %s" % [ name for name, cmd in self.cmds.items() if cmd.setterDisabled ])
        print("getterDisabled:         %s" % [ name for name, cmd in self.cmds.items() if cmd.getterDisabled ])
        print("readBack:               %s" % [ name for name, cmd in self.cmds.items() if cmd.readBack ])
        print("getFakeBufferLen:       %s" % [ name for name, cmd in self.cmds.items() if cmd.getFakeBufferLen ])
        print("setFakeBufferFromValue: %s" % [ name for name, cmd in self.cmds.items() if cmd.setFakeBufferFromValue ])
        print("setFakeLenFromValue:    %s" % [ name for name, cmd in self.cmds.items() if cmd.setFakeLenFromValue ])
        print("getter little-endian:   %s" % [ name for name, cmd in self.cmds.items() if     cmd.getLittleEndian and cmd.getter is not None ])
        print("getter big-endian:      %s" % [ name for name, cmd in self.cmds.items() if not cmd.getLittleEndian and cmd.getter is not None ])

    def countCommand(self):
        self.commandCount += 1
        
    def getSpectrumExternal(self):
        data = self.dev.read(0x82, self.block_size, timeout=self.timeout_ms)
        self.countCommand()
        if self.pixels == 2048:
            data.extend(self.dev.read(0x86, self.block_size, timeout=self.timeout_ms))
            self.countCommand()

        spectrum = [i + 256 * j for i, j in zip(data[::2], data[1::2])] # LSB-MSB

        if len(spectrum) != self.pixels:
            self.logError("getSpectrum: read %d pixels (expected %d)" % (len(spectrum), self.pixels))
            return False

        self.logInfo()
        self.logInfo("ACQUIRE_CCD: read %d pixels (%s)" % (len(spectrum), spectrum[:10]))
        #self.logInfo("ACQUIRE_CCD: nothing to read")#Hecox temp log statement
        self.logInfo()

        return True

    def getSpectrum(self):
        buf = [0] * 8
        self.pixels = 2048 #Hecox: temporary for FX2!!
        self.throttle_usb()
        self.dev.ctrl_transfer(HOST_TO_DEVICE, 0xad, 0, 0, buf, self.timeout_ms)
        self.countCommand()
        sleep(0.001) #Hecox: introduce a slight delay to test behavior of EP when it's not immediately read
        data = self.dev.read(0x82, self.block_size, timeout=self.timeout_ms)
        self.countCommand()
        if self.pixels == 2048:
            data.extend(self.dev.read(0x86, self.block_size, timeout=self.timeout_ms))
            self.countCommand()

        spectrum = [i + 256 * j for i, j in zip(data[::2], data[1::2])] # LSB-MSB

        if len(spectrum) != self.pixels:
            self.logError("getSpectrum: read %d pixels (expected %d)" % (len(spectrum), self.pixels))
            print(spectrum)
            return False

        self.logInfo()
        self.logInfo("ACQUIRE_CCD: read %d pixels (%s)" % (len(spectrum), spectrum[0:10]))
        #self.logInfo("ACQUIRE_CCD: nothing to read")#Hecox temp log statement
        for pixel_index in spectrum:
            if spectrum[pixel_index] == 655535:
                self.logInfo("First pixel at offset of %d pixels" % (pixel_index))
        self.logInfo()


        return True

    def getLastValue(self, name):
        if name in self.lastValues:
            return self.lastValues[name]
        return None

    def testSet(self, cmd, expectedValue):
        print("testget for " + str(cmd))
        if cmd.setter is None or cmd.setterDisabled:
            return False

        value = expectedValue[0]
        print("value=" + str(value))
        displayValue = expectedValue[1]
        print("displayValue=" + str(displayValue))
        
        try:
            (wValue, wIndex, buf_or_len) = cmd.buildPayload(value)
        except Exception as ex:
            self.logError("testSet: failed to build payload for %s value %s: %s" % (cmd, value, ex))
            return False

        if self.debug:
            print("  %s(%s) -> opcode 0x%02x, value 0x%04x, index 0x%04x, buf_or_len %s" % (
                cmd.setterName(), value, cmd.setter, wValue, wIndex, buf_or_len))

        self.throttle_usb()
        print("before transfer")
        result = self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd.setter, wValue, wIndex, buf_or_len, self.timeout_ms)
        print("after transfer")
        self.countCommand()

        if type(buf_or_len) is list:
            length = len(buf_or_len)
        else:
            length = buf_or_len

        if result != length:
            self.logError("testSet(%s) failed (wrote %d bytes, expected %d)" % (cmd, result, length))
            return False

        self.lastValues[cmd.name] = value

        self.logInfo("%-40s wrote %s" % (cmd.setterName(), displayValue))

        if cmd.setDelayMS > 0:
            sleep(cmd.setDelayMS / 1000.0)

        return True

    def testGet(self, cmd, expectedValue=None):
        if cmd.getter is None:
            return

        if cmd.getterDisabled:
            return self.logSkip(cmd.getterName(), "disabled")

        wValue = 0 
        wIndex = 0
        wLength = 64

        if cmd.wValue is not None:
            wValue = cmd.wValue

        if cmd.getFakeBufferLen is not None:
            wLength = [0] * cmd.getFakeBufferLen
        elif cmd.readBack is not None:
            wLength = cmd.readBack
        elif cmd.readLen is not None:
            wLength = cmd.readLen

        if cmd.wIndexRange is not None:
            wIndex = random.randrange(cmd.wIndexRange[0], cmd.wIndexRange[1])

        if self.debug:
            print("  %s -> opcode 0x%02x, value 0x%04x, index 0x%04x, len %s" % (
                cmd.getterName(), cmd.getter, wValue, wIndex, wLength))

        self.throttle_usb()
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd.getter, wValue, wIndex, wLength, self.timeout_ms)
        self.countCommand()

        (raw, rawDisplay, stringDisplay) = cmd.parseResult(result)
        if self.debug:
            print("  %s (opcode 0x%02x, value 0x%04x, index 0x%04x, len %s) -> %s -> %s (%s)" % (
                cmd.getterName(), cmd.getter, wValue, wIndex, wLength, result, stringDisplay, rawDisplay))

        if expectedValue is not None:
            if raw == expectedValue[0]:
                self.logInfo("%-40s returned expected %s (%s)" % (cmd.getterName(), rawDisplay, stringDisplay))
            else:
                self.logError("%s returned %s (expected %s)" % (cmd.getterName(), raw, expectedValue[0]))
                return False
        else:
            self.logInfo("%-40s returned %s (%s)" % (cmd.getterName(), rawDisplay, stringDisplay))

        return True

    def run(self, cmd):
        if self.debug:
            print("\nRunning: %s (dataType %s, %d errors)" % (cmd, cmd.dataType, self.errorCount))

        if cmd.usesLaser and not self.use_laser:
            return self.logSkip(cmd, "laser tests disabled")

        if cmd.requiresLaserModEnabled and not self.getLastValue("LASER_MOD_ENABLED"):
            self.testSet(self.cmds["LASER_MOD_ENABLED"], (1, "True"))

        if not cmd.isSupported(self.pid):
            return self.logSkip(cmd, "not supported on 0x%04x" % self.pid)

        if cmd.setter is None:
            # just test the getter
            return self.testGet(cmd)

        if cmd.setterDisabled:
            # just test the getter
            self.logSkip(cmd.setterName(), "disabled")
            return self.testGet(cmd)

        expectedValue = cmd.makeRandomValue()
        if expectedValue is None:
            self.logSkip(cmd.setterName(), "expectedValue None")
            return self.testGet(cmd)

        if self.testSet(cmd, expectedValue):
            return self.testGet(cmd, expectedValue)

    def runRandom(self):
        name = random.choice(list(self.cmds.keys()))
        cmd = self.cmds[name]
        self.run(cmd)

    def runSimple(self):
        name = self.simpleCommands[self.simpleIndex]
        cmd = self.cmds[name]
        self.run(cmd)
        self.simpleIndex = (self.simpleIndex + 1) % len(self.simpleCommands)

    def runAll(self):
        for name in sorted(self.cmds):
            self.run(self.cmds[name])

    def logError(self, msg):
        self.logInfo()
        self.logInfo("ERROR: %s" % msg)
        self.logInfo()
        self.errorCount += 1

    def logSkip(self, name, msg):
        self.logInfo("%-40s skipping: %s" % (name, msg))
        self.skipCount += 1

    def logInfo(self, msg=""):
        print("%s [%6d] %s" % (datetime.datetime.now(), self.commandCount, msg))

    def logHeader(self, msg):
        self.logInfo() 
        self.logInfo("================================================================================")
        self.logInfo(msg)
        self.logInfo("================================================================================")
        self.logInfo()

    def processArgs(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--pid", default="1000", choices=["1000", "2000", "4000"], help="USB Product ID")
        parser.add_argument("--count", type=int, default=5, help="how many commands to run between spectra")
        parser.add_argument("--pixels", type=int, help="spectrometer pixels, if non-standard for PID")
        parser.add_argument("--block-size", type=int, help="read length in bytes when reading spectra (default 2 * pixels)")
        parser.add_argument("--delay-ms", type=int, help="min delay between USB commands (ms)")
        parser.add_argument("--timeout-ms", type=int, default=1000, help="USB timeout (ms)")
        parser.add_argument("--max", type=int, help="maximum number of commands to test")
        parser.add_argument("--simple", action='store_true', help="simple command set")
        parser.add_argument("--externalAcq", action='store_true', help="run external acquisition with laser pulse")
        parser.add_argument("--report", action='store_true', help="generate an API report")
        parser.add_argument("--debug", action='store_true', help="verbose output")

        laser_parser = parser.add_mutually_exclusive_group(required=False)
        laser_parser.add_argument('--laser',    dest='use_laser', action='store_true')
        laser_parser.add_argument('--no-laser', dest='use_laser', action='store_false', help="disable laser-related tests")
        parser.set_defaults(use_laser=True)

        args = parser.parse_args()

        # copy results
        for field in ['pixels', 'block_size', 'debug', 'count', 'delay_ms', 'timeout_ms', 'simple', 'externalAcq', 'max', 'report', 'use_laser']:
            setattr(self, field, getattr(args, field))

        self.pid = int(args.pid, 16)

        # pixels
        if self.pixels is None:
            if self.pid == 0x2000:
                self.pixels = 512
            else:
                self.pixels = 1024

        # block size
        if self.block_size is None:
            if self.pixels == 2048:
                self.block_size = 2048
            else:
                self.block_size = self.pixels * 2
    
    #Executes the required commands for external spectrum acquisition
    def runExtAcq(self):
        #get spectrum by pulsing the laser for 50ms; then get the spectrum
        self.throttle_usb()
        cmd = APICommand("LASER_ENABLED",                getter=0xE2, setter=0xBE, dataType="Bool",    readLen=1, setRange=(1,1), usesLaser=True, setterDisabled=False, notes="disabled in test because dangerous")
        self.run(cmd)
        sleep(0.05)
        cmd = APICommand("LASER_ENABLED",                getter=0xE2, setter=0xBE, dataType="Bool",    readLen=1, setRange=(0,0), usesLaser=True, setterDisabled=False, notes="disabled in test because dangerous")
        self.run(cmd)
        self.getSpectrumExternal()

################################################################################
#                                                                              #
#                                    main()                                    #
#                                                                              #
################################################################################

fixture = TestFixture()
if fixture.report:
    fixture.apiReport()
    sys.exit()

if not fixture.enumerate():
    print("No matching spectrometers found.")
    sys.exit()

#if not fixture.simple:
#    fixture.logHeader("Quick test of all commands")
#    fixture.runAll()
#    fixture.resetCounts()

fixture.logHeader("Starting Monte Carlo testing")
fixture.logInfo("Press Ctrl-C to exit...\n")

try:
    #The below line was added by Hecox for testing integration-time command. For testing only
    #cmd = APICommand("INTEGRATION_TIME",             getter=0xBF, setter=0xB2, dataType="Uint24",  readLen=3, getLittleEndian=True, setRange=(500,500), readBack=6, notes="Integration time in ms or 10ms (see OPT_INT_TIME_RES) sent as 32-bit word: LSW as wValue, MSW as wIndex (big-endian within each)")
    #fixture.run(cmd)
    while True:
        break
        fixture.run(APICommand("CCD_SENSING_THRESHOLD",        getter=0xD1, setter=0xD0, dataType="Uint16",  readLen=2, setRange=(0, 5000), getLittleEndian=True))
    while True:
        if fixture.simple:
            #cmd = APICommand("INTEGRATION_TIME",             getter=0xBF, setter=0xB2, dataType="Uint24",  readLen=3, getLittleEndian=True, setRange=(10, 1000), readBack=6, notes="Integration time in ms or 10ms (see OPT_INT_TIME_RES) sent as 32-bit word: LSW as wValue, MSW as wIndex (big-endian within each)")
            #fixture.run(cmd)
            fixture.runSimple()
            fixture.getSpectrum()
        elif fixture.externalAcq:
            fixture.runExtAcq()
        else:
            #for i in range(fixture.count):
                #fixture.runRandom()    
            fixture.getSpectrum()
            
        if fixture.complete():
            print("%d commands completed successfully" % fixture.commandCount)
            break
except:
    print("Caught exception after %d commands sent (%d errors, %d skipped)" % (
        fixture.commandCount, fixture.errorCount, fixture.skipCount))
    traceback.print_exc()

print("Test ended after %.2f seconds" % fixture.duration()) 
