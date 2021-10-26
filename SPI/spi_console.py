from tkinter import *
from tkinter.ttk import *

import time
import threading
import board
import digitalio
import busio

spi  = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

ready = digitalio.DigitalInOut(board.D5)
ready.direction = digitalio.Direction.INPUT

trigger = digitalio.DigitalInOut(board.D6)
trigger.direction = digitalio.Direction.OUTPUT
trigger.value = False

class cFPGAConfig:
    IntTime     = 16
    Offset      = 0
    Gain        = 1
    ADBitWidth  = 12
    ODBitWidth  = 12
    StartLine   = 250
    StopLine    = 750
    StartColumn = 500
    StopColumn  = 1500

def fWriteIntTime():
    command     = bytearray(7)
    response    = bytearray(7)
    #Clear any garbage
    while ready.value:
        spi.readinto(response, 0, 2)
    command     = [0x3c, 0x00, 0x02, 0x91, cFPGAConfig.IntTime, 0xFF, 0x3E]
    print("Writing integration time of ", cFPGAConfig.IntTime, "ms.")
    spi.write(command, 0, 7)
 
def fWriteOffset():
    command     = bytearray(7)
    response    = bytearray(7)
    while ready.value:
        spi.readinto(response, 0, 2)
    command     = [0x3c, 0x00, 0x02, 0x93, cFPGAConfig.Offset, 0xFF, 0x3E]
    print("Writing offset of ", cFPGAConfig.Offset, ".")
    spi.write(command, 0, 7)
 
def fWriteGain():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    command     = [0x3c, 0x00, 0x03, 0x94, 0x00, cFPGAConfig.Gain, 0xFF, 0x3E]
    print("Writing gain of ", cFPGAConfig.Gain, "dB.")
    spi.write(command, 0, 8)
 
def fWriteStartLine():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StartLine0  = int(cFPGAConfig.StartLine % 256)
    StartLine1  = int(cFPGAConfig.StartLine / 256)
    command     = [0x3c, 0x00, 0x03, 0xD0, StartLine0, StartLine1, 0xFF, 0x3E]
    print("Writing start line of ", cFPGAConfig.StartLine, ".")
    spi.write(command, 0, 8)
 
def fWriteStopLine():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StopLine0   = int(cFPGAConfig.StopLine % 256)
    StopLine1   = int(cFPGAConfig.StopLine / 256)
    command     = [0x3c, 0x00, 0x03, 0xD1, StopLine0, StopLine1, 0xFF, 0x3E]
    print("Writing stop line of ", cFPGAConfig.StopLine, ".")
    spi.write(command, 0, 8)
 
def fWriteStartColumn():
    command         = bytearray(8)
    response        = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StartColumn0    = int(cFPGAConfig.StartColumn % 256)
    StartColumn1    = int(cFPGAConfig.StartColumn / 256)
    command         = [0x3c, 0x00, 0x03, 0xD2, StartColumn0, StartColumn1, 0xFF, 0x3E]
    print("Writing start column of ", cFPGAConfig.StartColumn, ".")
    spi.write(command, 0, 8)
 
def fWriteStopColumn():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StopColumn0 = int(cFPGAConfig.StopColumn % 256)
    StopColumn1 = int(cFPGAConfig.StopColumn / 256)
    command     = [0x3c, 0x00, 0x03, 0xD3, StopColumn0, StopColumn1, 0xFF, 0x3E]
    print("Writing start line of ", cFPGAConfig.StopColumn, ".")
    spi.write(command, 0, 8)
 
def fWriteResolution():
    command     = bytearray(7)
    response    = bytearray(7)
    while ready.value:
        spi.readinto(response, 0, 2)
    if   cFPGAConfig.ADBitWidth == 12 and cFPGAConfig.ODBitWidth == 12:
        Resolution = 0x3
    elif cFPGAConfig.ADBitWidth == 12 and cFPGAConfig.ODBitWidth == 10:
        Resolution = 0x2
    elif cFPGAConfig.ADBitWidth == 10 and cFPGAConfig.ODBitWidth == 12:
        Resolution = 0x1
    else:
        Resolution = 0x0    
    command     = [0x3c, 0x00, 0x02, 0xAB, Resolution, 0xFF, 0x3E]
    print("Writing resolution of ", hex(Resolution), ".")
    spi.write(command, 0, 7)
 
def fIntValidate(input):
    if input.isdigit():
        return True
                        
    elif input is "":
        return True

    else:
        return False

def fRegUpdate():
    if int(entIntTime.get()) != cFPGAConfig.IntTime:
        cFPGAConfig.IntTime = int(entIntTime.get())
        fWriteIntTime()
    if int(entOffset.get()) != cFPGAConfig.Offset:
        cFPGAConfig.Offset = int(entOffset.get())
        fWriteOffset()
    if int(entGain.get()) != cFPGAConfig.Gain:
        cFPGAConfig.Gain = int(entGain.get())
        fWriteGain()
    if int(entStartLine.get()) != cFPGAConfig.StartLine:
        cFPGAConfig.StartLine = int(entStartLine.get())
        fWriteStartLine()
    if int(entStopLine.get()) != cFPGAConfig.StopLine:
        cFPGAConfig.StopLine = int(entStopLine.get())
        fWriteStopLine()
    if int(entStartColumn.get()) != cFPGAConfig.StartColumn:
        cFPGAConfig.StartColumn = int(entStartColumn.get())
        fWriteStartColumn()
    if int(entStopColumn.get()) != cFPGAConfig.StopColumn:
        cFPGAConfig.StopColumn = int(entStopColumn.get())
        fWriteStopColumn()
    if int(entADBitWidth.get()) != cFPGAConfig.ADBitWidth or int(entODBitWidth.get()) != cFPGAConfig.ODBitWidth:
        cFPGAConfig.ADBitWidth = int(entADBitWidth.get())
        cFPGAConfig.ODBitWidth = int(entODBitWidth.get())
        fWriteResolution()

def fEEPROMStart():    
    def fEEPROMRead():
        EEPROMPage = bytearray(68)
        command = bytearray(7)
        page = int(entEEPROMPage.get())
        command = [0x3C, 0x00, 0x02, 0xB0, (0x40 + page), 0xFF, 0x3E]
        spi.write(command, 0, 7)
        time.sleep(0.01)
        command = [0x3C, 0x00, 0x01, 0x31, 0xFF, 0x3E]
        spi.write_readinto(command, EEPROMPage, 0, 6, 0, 68)
        strEEPROM0_0.set(str(hex(EEPROMPage[4])))
        strEEPROM0_1.set(str(hex(EEPROMPage[5])))
        strEEPROM0_2.set(str(hex(EEPROMPage[6])))
        strEEPROM0_3.set(str(hex(EEPROMPage[7])))
        strEEPROM0_4.set(str(hex(EEPROMPage[8])))
        strEEPROM0_5.set(str(hex(EEPROMPage[9])))
        strEEPROM0_6.set(str(hex(EEPROMPage[10])))
        strEEPROM0_7.set(str(hex(EEPROMPage[11])))
        strEEPROM1_0.set(str(hex(EEPROMPage[12])))
        strEEPROM1_1.set(str(hex(EEPROMPage[13])))
        strEEPROM1_2.set(str(hex(EEPROMPage[14])))
        strEEPROM1_3.set(str(hex(EEPROMPage[15])))
        strEEPROM1_4.set(str(hex(EEPROMPage[16])))
        strEEPROM1_5.set(str(hex(EEPROMPage[17])))
        strEEPROM1_6.set(str(hex(EEPROMPage[18])))
        strEEPROM1_7.set(str(hex(EEPROMPage[19])))
        strEEPROM2_0.set(str(hex(EEPROMPage[20])))
        strEEPROM2_1.set(str(hex(EEPROMPage[21])))
        strEEPROM2_2.set(str(hex(EEPROMPage[22])))
        strEEPROM2_3.set(str(hex(EEPROMPage[23])))
        strEEPROM2_4.set(str(hex(EEPROMPage[24])))
        strEEPROM2_5.set(str(hex(EEPROMPage[25])))
        strEEPROM2_6.set(str(hex(EEPROMPage[26])))
        strEEPROM2_7.set(str(hex(EEPROMPage[27])))
        strEEPROM3_0.set(str(hex(EEPROMPage[28])))
        strEEPROM3_1.set(str(hex(EEPROMPage[29])))
        strEEPROM3_2.set(str(hex(EEPROMPage[30])))
        strEEPROM3_3.set(str(hex(EEPROMPage[31])))
        strEEPROM3_4.set(str(hex(EEPROMPage[32])))
        strEEPROM3_5.set(str(hex(EEPROMPage[33])))
        strEEPROM3_6.set(str(hex(EEPROMPage[34])))
        strEEPROM3_7.set(str(hex(EEPROMPage[35])))
        strEEPROM4_0.set(str(hex(EEPROMPage[36])))
        strEEPROM4_1.set(str(hex(EEPROMPage[37])))
        strEEPROM4_2.set(str(hex(EEPROMPage[38])))
        strEEPROM4_3.set(str(hex(EEPROMPage[39])))
        strEEPROM4_4.set(str(hex(EEPROMPage[40])))
        strEEPROM4_5.set(str(hex(EEPROMPage[41])))
        strEEPROM4_6.set(str(hex(EEPROMPage[42])))
        strEEPROM4_7.set(str(hex(EEPROMPage[43])))
        strEEPROM5_0.set(str(hex(EEPROMPage[44])))
        strEEPROM5_1.set(str(hex(EEPROMPage[45])))
        strEEPROM5_2.set(str(hex(EEPROMPage[46])))
        strEEPROM5_3.set(str(hex(EEPROMPage[47])))
        strEEPROM5_4.set(str(hex(EEPROMPage[48])))
        strEEPROM5_5.set(str(hex(EEPROMPage[49])))
        strEEPROM5_6.set(str(hex(EEPROMPage[50])))
        strEEPROM5_7.set(str(hex(EEPROMPage[51])))
        strEEPROM6_0.set(str(hex(EEPROMPage[52])))
        strEEPROM6_1.set(str(hex(EEPROMPage[53])))
        strEEPROM6_2.set(str(hex(EEPROMPage[54])))
        strEEPROM6_3.set(str(hex(EEPROMPage[55])))
        strEEPROM6_4.set(str(hex(EEPROMPage[56])))
        strEEPROM6_5.set(str(hex(EEPROMPage[57])))
        strEEPROM6_6.set(str(hex(EEPROMPage[58])))
        strEEPROM6_7.set(str(hex(EEPROMPage[59])))
        strEEPROM7_0.set(str(hex(EEPROMPage[60])))
        strEEPROM7_1.set(str(hex(EEPROMPage[61])))
        strEEPROM7_2.set(str(hex(EEPROMPage[62])))
        strEEPROM7_3.set(str(hex(EEPROMPage[63])))
        strEEPROM7_4.set(str(hex(EEPROMPage[64])))
        strEEPROM7_5.set(str(hex(EEPROMPage[65])))
        strEEPROM7_6.set(str(hex(EEPROMPage[66])))
        strEEPROM7_7.set(str(hex(EEPROMPage[67])))

    def fEEPROMWrite():
        page        = int(entEEPROMPage.get())
        command     = bytearray(7)
        EEPROMWrCmd = bytearray(70)
        EEPROMWrCmd[0] = 0x3C
        EEPROMWrCmd[1] = 0x00
        EEPROMWrCmd[2] = 0x41
        EEPROMWrCmd[3] = 0xB1
        EEPROMWrCmd[4] = int(strEEPROM0_0.get(), 16)
        EEPROMWrCmd[5] = int(strEEPROM0_1.get(), 16)
        EEPROMWrCmd[6] = int(strEEPROM0_2.get(), 16)
        EEPROMWrCmd[7] = int(strEEPROM0_3.get(), 16)
        EEPROMWrCmd[8] = int(strEEPROM0_4.get(), 16)
        EEPROMWrCmd[9] = int(strEEPROM0_5.get(), 16)
        EEPROMWrCmd[10] = int(strEEPROM0_6.get(), 16)
        EEPROMWrCmd[11] = int(strEEPROM0_7.get(), 16)
        EEPROMWrCmd[12] = int(strEEPROM1_0.get(), 16)
        EEPROMWrCmd[13] = int(strEEPROM1_1.get(), 16)
        EEPROMWrCmd[14] = int(strEEPROM1_2.get(), 16)
        EEPROMWrCmd[15] = int(strEEPROM1_3.get(), 16)
        EEPROMWrCmd[16] = int(strEEPROM1_4.get(), 16)
        EEPROMWrCmd[17] = int(strEEPROM1_5.get(), 16)
        EEPROMWrCmd[18] = int(strEEPROM1_6.get(), 16)
        EEPROMWrCmd[19] = int(strEEPROM1_7.get(), 16)
        EEPROMWrCmd[20] = int(strEEPROM2_0.get(), 16)
        EEPROMWrCmd[21] = int(strEEPROM2_1.get(), 16)
        EEPROMWrCmd[22] = int(strEEPROM2_2.get(), 16)
        EEPROMWrCmd[23] = int(strEEPROM2_3.get(), 16)
        EEPROMWrCmd[24] = int(strEEPROM2_4.get(), 16)
        EEPROMWrCmd[25] = int(strEEPROM2_5.get(), 16)
        EEPROMWrCmd[26] = int(strEEPROM2_6.get(), 16)
        EEPROMWrCmd[27] = int(strEEPROM2_7.get(), 16)
        EEPROMWrCmd[28] = int(strEEPROM3_0.get(), 16)
        EEPROMWrCmd[29] = int(strEEPROM3_1.get(), 16)
        EEPROMWrCmd[30] = int(strEEPROM3_2.get(), 16)
        EEPROMWrCmd[31] = int(strEEPROM3_3.get(), 16)
        EEPROMWrCmd[32] = int(strEEPROM3_4.get(), 16)
        EEPROMWrCmd[33] = int(strEEPROM3_5.get(), 16)
        EEPROMWrCmd[34] = int(strEEPROM3_6.get(), 16)
        EEPROMWrCmd[35] = int(strEEPROM3_7.get(), 16)
        EEPROMWrCmd[36] = int(strEEPROM4_0.get(), 16)
        EEPROMWrCmd[37] = int(strEEPROM4_1.get(), 16)
        EEPROMWrCmd[38] = int(strEEPROM4_2.get(), 16)
        EEPROMWrCmd[39] = int(strEEPROM4_3.get(), 16)
        EEPROMWrCmd[40] = int(strEEPROM4_4.get(), 16)
        EEPROMWrCmd[41] = int(strEEPROM4_5.get(), 16)
        EEPROMWrCmd[42] = int(strEEPROM4_6.get(), 16)
        EEPROMWrCmd[43] = int(strEEPROM4_7.get(), 16)
        EEPROMWrCmd[44] = int(strEEPROM5_0.get(), 16)
        EEPROMWrCmd[45] = int(strEEPROM5_1.get(), 16)
        EEPROMWrCmd[46] = int(strEEPROM5_2.get(), 16)
        EEPROMWrCmd[47] = int(strEEPROM5_3.get(), 16)
        EEPROMWrCmd[48] = int(strEEPROM5_4.get(), 16)
        EEPROMWrCmd[49] = int(strEEPROM5_5.get(), 16)
        EEPROMWrCmd[50] = int(strEEPROM5_6.get(), 16)
        EEPROMWrCmd[51] = int(strEEPROM5_7.get(), 16)
        EEPROMWrCmd[52] = int(strEEPROM6_0.get(), 16)
        EEPROMWrCmd[53] = int(strEEPROM6_1.get(), 16)
        EEPROMWrCmd[54] = int(strEEPROM6_2.get(), 16)
        EEPROMWrCmd[55] = int(strEEPROM6_3.get(), 16)
        EEPROMWrCmd[56] = int(strEEPROM6_4.get(), 16)
        EEPROMWrCmd[57] = int(strEEPROM6_5.get(), 16)
        EEPROMWrCmd[58] = int(strEEPROM6_6.get(), 16)
        EEPROMWrCmd[59] = int(strEEPROM6_7.get(), 16)
        EEPROMWrCmd[60] = int(strEEPROM7_0.get(), 16)
        EEPROMWrCmd[61] = int(strEEPROM7_1.get(), 16)
        EEPROMWrCmd[62] = int(strEEPROM7_2.get(), 16)
        EEPROMWrCmd[63] = int(strEEPROM7_3.get(), 16)
        EEPROMWrCmd[64] = int(strEEPROM7_4.get(), 16)
        EEPROMWrCmd[65] = int(strEEPROM7_5.get(), 16)
        EEPROMWrCmd[66] = int(strEEPROM7_6.get(), 16)
        EEPROMWrCmd[67] = int(strEEPROM7_7.get(), 16)
        EEPROMWrCmd[68] = 0xFF
        EEPROMWrCmd[69] = 0x3E
        spi.write(EEPROMWrCmd, 0, 70)
        command = [0x3c, 0x00, 0x02, 0xB0, (0x80 + page), 0xFF, 0x3E]
        spi.write(command, 0, 7)

    winEEPROM = Tk()
    winEEPROM.title("EEPROM Utility")
    frEEPROM    = Frame(winEEPROM)
    strEEPROM0_0   = StringVar(frEEPROM)
    entEEPROM0_0   = Entry(frEEPROM, textvariable = strEEPROM0_0, width = 5)
    entEEPROM0_0.grid(row=0, column=0)
    strEEPROM0_1   = StringVar(frEEPROM)
    entEEPROM0_1   = Entry(frEEPROM, textvariable = strEEPROM0_1, width = 5)
    entEEPROM0_1.grid(row=0, column=1)
    strEEPROM0_2   = StringVar(frEEPROM)
    entEEPROM0_2   = Entry(frEEPROM, textvariable = strEEPROM0_2, width = 5)
    entEEPROM0_2.grid(row=0, column=2)
    strEEPROM0_3   = StringVar(frEEPROM)
    entEEPROM0_3   = Entry(frEEPROM, textvariable = strEEPROM0_3, width = 5)
    entEEPROM0_3.grid(row=0, column=3)
    strEEPROM0_4   = StringVar(frEEPROM)
    entEEPROM0_4   = Entry(frEEPROM, textvariable = strEEPROM0_4, width = 5)
    entEEPROM0_4.grid(row=0, column=4)
    strEEPROM0_5   = StringVar(frEEPROM)
    entEEPROM0_5   = Entry(frEEPROM, textvariable = strEEPROM0_5, width = 5)
    entEEPROM0_5.grid(row=0, column=5)
    strEEPROM0_6   = StringVar(frEEPROM)
    entEEPROM0_6   = Entry(frEEPROM, textvariable = strEEPROM0_6, width = 5)
    entEEPROM0_6.grid(row=0, column=6)
    strEEPROM0_7   = StringVar(frEEPROM)
    entEEPROM0_7   = Entry(frEEPROM, textvariable = strEEPROM0_7, width = 5)
    entEEPROM0_7.grid(row=0, column=7)
    strEEPROM1_0   = StringVar(frEEPROM)
    entEEPROM1_0   = Entry(frEEPROM, textvariable = strEEPROM1_0, width = 5)
    entEEPROM1_0.grid(row=1, column=0)
    strEEPROM1_1   = StringVar(frEEPROM)
    entEEPROM1_1   = Entry(frEEPROM, textvariable = strEEPROM1_1, width = 5)
    entEEPROM1_1.grid(row=1, column=1)
    strEEPROM1_2   = StringVar(frEEPROM)
    entEEPROM1_2   = Entry(frEEPROM, textvariable = strEEPROM1_2, width = 5)
    entEEPROM1_2.grid(row=1, column=2)
    strEEPROM1_3   = StringVar(frEEPROM)
    entEEPROM1_3   = Entry(frEEPROM, textvariable = strEEPROM1_3, width = 5)
    entEEPROM1_3.grid(row=1, column=3)
    strEEPROM1_4   = StringVar(frEEPROM)
    entEEPROM1_4   = Entry(frEEPROM, textvariable = strEEPROM1_4, width = 5)
    entEEPROM1_4.grid(row=1, column=4)
    strEEPROM1_5   = StringVar(frEEPROM)
    entEEPROM1_5   = Entry(frEEPROM, textvariable = strEEPROM1_5, width = 5)
    entEEPROM1_5.grid(row=1, column=5)
    strEEPROM1_6   = StringVar(frEEPROM)
    entEEPROM1_6   = Entry(frEEPROM, textvariable = strEEPROM1_6, width = 5)
    entEEPROM1_6.grid(row=1, column=6)
    strEEPROM1_7   = StringVar(frEEPROM)
    entEEPROM1_7   = Entry(frEEPROM, textvariable = strEEPROM1_7, width = 5)
    entEEPROM1_7.grid(row=1, column=7)
    strEEPROM2_0   = StringVar(frEEPROM)
    entEEPROM2_0   = Entry(frEEPROM, textvariable = strEEPROM2_0, width = 5)
    entEEPROM2_0.grid(row=2, column=0)
    strEEPROM2_1   = StringVar(frEEPROM)
    entEEPROM2_1   = Entry(frEEPROM, textvariable = strEEPROM2_1, width = 5)
    entEEPROM2_1.grid(row=2, column=1)
    strEEPROM2_2   = StringVar(frEEPROM)
    entEEPROM2_2   = Entry(frEEPROM, textvariable = strEEPROM2_2, width = 5)
    entEEPROM2_2.grid(row=2, column=2)
    strEEPROM2_3   = StringVar(frEEPROM)
    entEEPROM2_3   = Entry(frEEPROM, textvariable = strEEPROM2_3, width = 5)
    entEEPROM2_3.grid(row=2, column=3)
    strEEPROM2_4   = StringVar(frEEPROM)
    entEEPROM2_4   = Entry(frEEPROM, textvariable = strEEPROM2_4, width = 5)
    entEEPROM2_4.grid(row=2, column=4)
    strEEPROM2_5   = StringVar(frEEPROM)
    entEEPROM2_5   = Entry(frEEPROM, textvariable = strEEPROM2_5, width = 5)
    entEEPROM2_5.grid(row=2, column=5)
    strEEPROM2_6   = StringVar(frEEPROM)
    entEEPROM2_6   = Entry(frEEPROM, textvariable = strEEPROM2_6, width = 5)
    entEEPROM2_6.grid(row=2, column=6)
    strEEPROM2_7   = StringVar(frEEPROM)
    entEEPROM2_7   = Entry(frEEPROM, textvariable = strEEPROM2_7, width = 5)
    entEEPROM2_7.grid(row=2, column=7)
    strEEPROM3_0   = StringVar(frEEPROM)
    entEEPROM3_0   = Entry(frEEPROM, textvariable = strEEPROM3_0, width = 5)
    entEEPROM3_0.grid(row=3, column=0)
    strEEPROM3_1   = StringVar(frEEPROM)
    entEEPROM3_1   = Entry(frEEPROM, textvariable = strEEPROM3_1, width = 5)
    entEEPROM3_1.grid(row=3, column=1)
    strEEPROM3_2   = StringVar(frEEPROM)
    entEEPROM3_2   = Entry(frEEPROM, textvariable = strEEPROM3_2, width = 5)
    entEEPROM3_2.grid(row=3, column=2)
    strEEPROM3_3   = StringVar(frEEPROM)
    entEEPROM3_3   = Entry(frEEPROM, textvariable = strEEPROM3_3, width = 5)
    entEEPROM3_3.grid(row=3, column=3)
    strEEPROM3_4   = StringVar(frEEPROM)
    entEEPROM3_4   = Entry(frEEPROM, textvariable = strEEPROM3_4, width = 5)
    entEEPROM3_4.grid(row=3, column=4)
    strEEPROM3_5   = StringVar(frEEPROM)
    entEEPROM3_5   = Entry(frEEPROM, textvariable = strEEPROM3_5, width = 5)
    entEEPROM3_5.grid(row=3, column=5)
    strEEPROM3_6   = StringVar(frEEPROM)
    entEEPROM3_6   = Entry(frEEPROM, textvariable = strEEPROM3_6, width = 5)
    entEEPROM3_6.grid(row=3, column=6)
    strEEPROM3_7   = StringVar(frEEPROM)
    entEEPROM3_7   = Entry(frEEPROM, textvariable = strEEPROM3_7, width = 5)
    entEEPROM3_7.grid(row=3, column=7)
    strEEPROM4_0   = StringVar(frEEPROM)
    entEEPROM4_0   = Entry(frEEPROM, textvariable = strEEPROM4_0, width = 5)
    entEEPROM4_0.grid(row=4, column=0)
    strEEPROM4_1   = StringVar(frEEPROM)
    entEEPROM4_1   = Entry(frEEPROM, textvariable = strEEPROM4_1, width = 5)
    entEEPROM4_1.grid(row=4, column=1)
    strEEPROM4_2   = StringVar(frEEPROM)
    entEEPROM4_2   = Entry(frEEPROM, textvariable = strEEPROM4_2, width = 5)
    entEEPROM4_2.grid(row=4, column=2)
    strEEPROM4_3   = StringVar(frEEPROM)
    entEEPROM4_3   = Entry(frEEPROM, textvariable = strEEPROM4_3, width = 5)
    entEEPROM4_3.grid(row=4, column=3)
    strEEPROM4_4   = StringVar(frEEPROM)
    entEEPROM4_4   = Entry(frEEPROM, textvariable = strEEPROM4_4, width = 5)
    entEEPROM4_4.grid(row=4, column=4)
    strEEPROM4_5   = StringVar(frEEPROM)
    entEEPROM4_5   = Entry(frEEPROM, textvariable = strEEPROM4_5, width = 5)
    entEEPROM4_5.grid(row=4, column=5)
    strEEPROM4_6   = StringVar(frEEPROM)
    entEEPROM4_6   = Entry(frEEPROM, textvariable = strEEPROM4_6, width = 5)
    entEEPROM4_6.grid(row=4, column=6)
    strEEPROM4_7   = StringVar(frEEPROM)
    entEEPROM4_7   = Entry(frEEPROM, textvariable = strEEPROM4_7, width = 5)
    entEEPROM4_7.grid(row=4, column=7)
    strEEPROM5_0   = StringVar(frEEPROM)
    entEEPROM5_0   = Entry(frEEPROM, textvariable = strEEPROM5_0, width = 5)
    entEEPROM5_0.grid(row=5, column=0)
    strEEPROM5_1   = StringVar(frEEPROM)
    entEEPROM5_1   = Entry(frEEPROM, textvariable = strEEPROM5_1, width = 5)
    entEEPROM5_1.grid(row=5, column=1)
    strEEPROM5_2   = StringVar(frEEPROM)
    entEEPROM5_2   = Entry(frEEPROM, textvariable = strEEPROM5_2, width = 5)
    entEEPROM5_2.grid(row=5, column=2)
    strEEPROM5_3   = StringVar(frEEPROM)
    entEEPROM5_3   = Entry(frEEPROM, textvariable = strEEPROM5_3, width = 5)
    entEEPROM5_3.grid(row=5, column=3)
    strEEPROM5_4   = StringVar(frEEPROM)
    entEEPROM5_4   = Entry(frEEPROM, textvariable = strEEPROM5_4, width = 5)
    entEEPROM5_4.grid(row=5, column=4)
    strEEPROM5_5   = StringVar(frEEPROM)
    entEEPROM5_5   = Entry(frEEPROM, textvariable = strEEPROM5_5, width = 5)
    entEEPROM5_5.grid(row=5, column=5)
    strEEPROM5_6   = StringVar(frEEPROM)
    entEEPROM5_6   = Entry(frEEPROM, textvariable = strEEPROM5_6, width = 5)
    entEEPROM5_6.grid(row=5, column=6)
    strEEPROM5_7   = StringVar(frEEPROM)
    entEEPROM5_7   = Entry(frEEPROM, textvariable = strEEPROM5_7, width = 5)
    entEEPROM5_7.grid(row=5, column=7)
    strEEPROM6_0   = StringVar(frEEPROM)
    entEEPROM6_0   = Entry(frEEPROM, textvariable = strEEPROM6_0, width = 5)
    entEEPROM6_0.grid(row=6, column=0)
    strEEPROM6_1   = StringVar(frEEPROM)
    entEEPROM6_1   = Entry(frEEPROM, textvariable = strEEPROM6_1, width = 5)
    entEEPROM6_1.grid(row=6, column=1)
    strEEPROM6_2   = StringVar(frEEPROM)
    entEEPROM6_2   = Entry(frEEPROM, textvariable = strEEPROM6_2, width = 5)
    entEEPROM6_2.grid(row=6, column=2)
    strEEPROM6_3   = StringVar(frEEPROM)
    entEEPROM6_3   = Entry(frEEPROM, textvariable = strEEPROM6_3, width = 5)
    entEEPROM6_3.grid(row=6, column=3)
    strEEPROM6_4   = StringVar(frEEPROM)
    entEEPROM6_4   = Entry(frEEPROM, textvariable = strEEPROM6_4, width = 5)
    entEEPROM6_4.grid(row=6, column=4)
    strEEPROM6_5   = StringVar(frEEPROM)
    entEEPROM6_5   = Entry(frEEPROM, textvariable = strEEPROM6_5, width = 5)
    entEEPROM6_5.grid(row=6, column=5)
    strEEPROM6_6   = StringVar(frEEPROM)
    entEEPROM6_6   = Entry(frEEPROM, textvariable = strEEPROM6_6, width = 5)
    entEEPROM6_6.grid(row=6, column=6)
    strEEPROM6_7   = StringVar(frEEPROM)
    entEEPROM6_7   = Entry(frEEPROM, textvariable = strEEPROM6_7, width = 5)
    entEEPROM6_7.grid(row=6, column=7)
    strEEPROM7_0   = StringVar(frEEPROM)
    entEEPROM7_0   = Entry(frEEPROM, textvariable = strEEPROM7_0, width = 5)
    entEEPROM7_0.grid(row=7, column=0)
    strEEPROM7_1   = StringVar(frEEPROM)
    entEEPROM7_1   = Entry(frEEPROM, textvariable = strEEPROM7_1, width = 5)
    entEEPROM7_1.grid(row=7, column=1)
    strEEPROM7_2   = StringVar(frEEPROM)
    entEEPROM7_2   = Entry(frEEPROM, textvariable = strEEPROM7_2, width = 5)
    entEEPROM7_2.grid(row=7, column=2)
    strEEPROM7_3   = StringVar(frEEPROM)
    entEEPROM7_3   = Entry(frEEPROM, textvariable = strEEPROM7_3, width = 5)
    entEEPROM7_3.grid(row=7, column=3)
    strEEPROM7_4   = StringVar(frEEPROM)
    entEEPROM7_4   = Entry(frEEPROM, textvariable = strEEPROM7_4, width = 5)
    entEEPROM7_4.grid(row=7, column=4)
    strEEPROM7_5   = StringVar(frEEPROM)
    entEEPROM7_5   = Entry(frEEPROM, textvariable = strEEPROM7_5, width = 5)
    entEEPROM7_5.grid(row=7, column=5)
    strEEPROM7_6   = StringVar(frEEPROM)
    entEEPROM7_6   = Entry(frEEPROM, textvariable = strEEPROM7_6, width = 5)
    entEEPROM7_6.grid(row=7, column=6)
    strEEPROM7_7   = StringVar(frEEPROM)
    entEEPROM7_7   = Entry(frEEPROM, textvariable = strEEPROM7_7, width = 5)
    entEEPROM7_7.grid(row=7, column=7)
    strEEPROMPage   = StringVar(frEEPROM, str(0))
    lblEEPROMPage   = Label(frEEPROM, text = 'EEPROM Page').grid(row=8, column=1)
    entEEPROMPage   = Entry(frEEPROM, textvariable = strEEPROMPage, validate="key", validatecommand=(cbEEPROMIntValidate, '%P'), width = 5)
    entEEPROMPage.grid(row=8, column=2)

    btnEEPROMRead   = Button(frEEPROM, text='Read Page', command=fEEPROMRead)
    btnEEPROMRead.grid(row=8, column=4)
    btnEEPROMWrite   = Button(frEEPROM, text='Write Page', command=fEEPROMWrite)
    btnEEPROMWrite.grid(row=8, column=6)

    col_count, row_count = frEEPROM.grid_size()
    for column in range(col_count):
        frEEPROM.grid_columnconfigure(column, minsize = 75)
    for row in range(row_count):
        frEEPROM.grid_rowconfigure(row, minsize=30)

    frEEPROM.pack()

    fEEPROMRead()
    winEEPROM.mainloop()


def fCapture():
    SPIBuf = bytearray(2)
    pixel=0
    pixel_num = []
    spectra = []
    # Send and acquire trigger
    trigger.value = True

    # Wait until the data is ready
    while not ready.value:
        pass

    # Relase the trigger
    trigger.value = False

    # Read in the spectra
    maxvalue = 0
    minvalue = 65536
    while ready.value:
        spi.readinto(SPIBuf, 0, 2)
        pixel = (SPIBuf[0] * 256) + SPIBuf[1]
        if pixel > maxvalue:
            maxvalue = pixel
        if pixel < minvalue:
            minvalue = pixel
        spectra.append(pixel)

    scale = maxvalue - minvalue
    midvalue = int(minvalue + (scale/2))
    cSpectra.delete("all")
    cSpectra.create_text(20,20,text=str(maxvalue), fill="white")
    cSpectra.create_text(20,270,text=str(midvalue), fill="white")
    cSpectra.create_text(20,520,text=str(minvalue), fill="white")
    spectraCount = int(len(spectra)/2)
    lastCount = int((spectra[0] + spectra[1])/2)
    for x in range(1, (spectraCount-1)):
        newCount = int((spectra[(x*2)] + spectra[((x*2) + 1)])/2)
        x0 = int(((x*2)/spectraCount)*920) + 40
        y0 = 540 - int(((lastCount-minvalue)/scale)*540)
        x1 = int((((x*2)+1)/spectraCount)*920) + 40
        y1 = 540 - int(((newCount-minvalue)/scale)*540)
        cSpectra.create_line(x0, y0, x1, y1, fill="green", width=1)
        lastCount = newCount

    winRoot.after(2, fCapture)

        
FPGAConfig      = cFPGAConfig()

winRoot = Tk()
winRoot.title("SPI SIG")
frControl   = Frame(winRoot)
frDraw      = Frame(winRoot)

cbControlIntValidate = winRoot.register(fIntValidate)
cbEEPROMIntValidate = winRoot.register(fIntValidate)

strIntTime      = StringVar(frControl, str(FPGAConfig.IntTime))
lblIntTime      = Label(frControl, text = 'Integration Time').grid(row=0)
entIntTime      = Entry(frControl, textvariable = strIntTime, validate="key", validatecommand=(cbControlIntValidate, '%P'), width = 5)
entIntTime.grid(row=0, column=1)

strOffset       = StringVar(frControl, str(FPGAConfig.Offset))
lblOffset       = Label(frControl, text = 'CCD Offset').grid(row=1)
entOffset       = Entry(frControl, textvariable = strOffset, validate="key", validatecommand=(cbControlIntValidate, '%P'), width = 5)
entOffset.grid(row=1, column=1)

strGain         = StringVar(frControl, str(FPGAConfig.Gain))
lblGain         = Label(frControl, text = 'CCD Gain').grid(row=2)
entGain         = Entry(frControl, textvariable = strGain, validate="key", validatecommand=(cbControlIntValidate, '%P'), width = 5)
entGain.grid(row=2, column=1)

strStartLine    = StringVar(frControl, str(FPGAConfig.StartLine))
lblStartLine    = Label(frControl, text = 'Start Line').grid(row=3)
entStartLine    = Entry(frControl, textvariable = strStartLine, validate="key", validatecommand=(cbControlIntValidate, '%P'), width = 5)
entStartLine.grid(row=3, column=1)

strStopLine     = StringVar(frControl, str(FPGAConfig.StopLine))
lblStopLine     = Label(frControl, text = 'Stop Line').grid(row=4)
entStopLine     = Entry(frControl, textvariable = strStopLine, validate="key", validatecommand=(cbControlIntValidate, '%P'), width = 5)
entStopLine.grid(row=4, column=1)

strStartColumn  = StringVar(frControl, str(FPGAConfig.StartColumn))
lblStartColumn  = Label(frControl, text = 'Start Column').grid(row=5)
entStartColumn  = Entry(frControl, textvariable = strStartColumn, validate="key", validatecommand=(cbControlIntValidate, '%P'), width = 5)
entStartColumn.grid(row=5, column=1)

strStopColumn   = StringVar(frControl, str(FPGAConfig.StopColumn))
lblStopColumn   = Label(frControl, text = 'Stop Column').grid(row=6)
entStopColumn   = Entry(frControl, textvariable = strStopColumn, validate="key", validatecommand=(cbControlIntValidate, '%P'), width = 5)
entStopColumn.grid(row=6, column=1)

strADBitWidth   = StringVar(frControl)
lblADBitWidth   = Label(frControl, text = 'AD Bit Width').grid(row=7)
entADBitWidth   = Combobox(frControl, textvariable = strADBitWidth, width = 4)
entADBitWidth.grid(row=7, column=1)
entADBitWidth['values'] = ('10', '12')
entADBitWidth['state']  = 'readonly'
entADBitWidth.current(1)

strODBitWidth   = StringVar(frControl)
lblODBitWidth   = Label(frControl, text = 'OD Bit Width').grid(row=8)
entODBitWidth   = Combobox(frControl, textvariable = strODBitWidth, width = 4)
entODBitWidth.grid(row=8, column=1)
entODBitWidth['values'] = ('10', '12')
entODBitWidth['state']  = 'readonly'
entODBitWidth.current(1)

btnCapture      = Button(frControl, text='Update', command=fRegUpdate)
btnCapture.grid(row=9, column=0)

btnEEPROM       = Button(frControl, text='EEPROM', command=fEEPROMStart)
btnEEPROM.grid(row=9, column=1)

cSpectra = Canvas(frDraw, bg="black", height=540, width=960)
cSpectra.pack()
col_count, row_count = frControl.grid_size()

frControl.grid_columnconfigure(0, minsize=110)
frControl.grid_columnconfigure(1, minsize=100)

for row in range(row_count):
    frControl.grid_rowconfigure(row, minsize=30)

# Take control of the SPI Bus
while not spi.try_lock():
    pass

# Configure the SPI bus
spi.configure(baudrate=8000000, phase=0, polarity=0, bits=8)

# Write initial config
fWriteIntTime()
fWriteOffset()
fWriteGain()
fWriteStartLine()
fWriteStopLine()
fWriteStartColumn()
fWriteStopColumn()
fWriteResolution()

# Launch the GUI
frControl.grid(row=0, column=0)
frDraw.grid(row=0, column=1)
winRoot.after(2, fCapture)
winRoot.mainloop()
