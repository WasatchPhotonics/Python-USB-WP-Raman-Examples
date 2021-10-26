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
        for x in range(0, 64):
            strEEPROM[x].set(str(hex(EEPROMPage[x+4])))

    def fEEPROMWrite():
        page        = int(entEEPROMPage.get())
        command     = bytearray(7)
        EEPROMWrCmd = bytearray(70)
        EEPROMWrCmd[0] = 0x3C
        EEPROMWrCmd[1] = 0x00
        EEPROMWrCmd[2] = 0x41
        EEPROMWrCmd[3] = 0xB1
        for x in range(0, 64):
            EEPROMWrCmd[x+4] = int(strEEPROM[x].get(), 16)

        EEPROMWrCmd[68] = 0xFF
        EEPROMWrCmd[69] = 0x3E
        spi.write(EEPROMWrCmd, 0, 70)
        command = [0x3c, 0x00, 0x02, 0xB0, (0x80 + page), 0xFF, 0x3E]
        spi.write(command, 0, 7)

    winEEPROM = Tk()
    winEEPROM.title("EEPROM Utility")
    frEEPROM    = Frame(winEEPROM)
    strEEPROM   = []
    entEEPROM   = []
    for x in range(0, 64):
        strEEPROM.append(StringVar(frEEPROM))
    for x in range(0, 64):
        entEEPROM.append(Entry(frEEPROM, textvariable = strEEPROM[x], width = 5))
    for x in range(0, 8):
        for y in range(0, 8):
            entEEPROM[((x*8)+y)].grid(row=x, column=y)

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
