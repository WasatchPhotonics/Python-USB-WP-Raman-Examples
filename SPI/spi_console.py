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
    ADBit       = 12
    ODBit       = 12
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
    spi.write(command, 0, 7)
 
def fWriteStartLine():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StartLine0  = int(cFPGAConfig.StartLine % 256)
    StartLine1  = int(cFPGAConfig.StartLine / 256)
    command     = [0x3c, 0x00, 0x03, 0xD0, StartLine0, StartLine1, 0xFF, 0x3E]
    print("Writing start line of ", cFPGAConfig.StartLine, ".")
    spi.write(command, 0, 7)
 
def fWriteStopLine():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StopLine0   = int(cFPGAConfig.StopLine % 256)
    StopLine1   = int(cFPGAConfig.StopLine / 256)
    command     = [0x3c, 0x00, 0x03, 0xD1, StopLine0, StopLine1, 0xFF, 0x3E]
    print("Writing stop line of ", cFPGAConfig.StopLine, ".")
    spi.write(command, 0, 7)
 
def fWriteStartColumn():
    command         = bytearray(8)
    response        = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StartColumn0    = int(cFPGAConfig.StartColumn % 256)
    StartColumn1    = int(cFPGAConfig.StartColumn / 256)
    command         = [0x3c, 0x00, 0x03, 0xD2, StartColumn0, StartColumn1, 0xFF, 0x3E]
    print("Writing start column of ", cFPGAConfig.StartColumn, ".")
    spi.write(command, 0, 7)
 
def fWriteStopColumn():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StopColumn0 = int(cFPGAConfig.StopColumn % 256)
    StopColumn1 = int(cFPGAConfig.StopColumn / 256)
    command     = [0x3c, 0x00, 0x03, 0xD3, StopColumn0, StopColumn1, 0xFF, 0x3E]
    print("Writing start line of ", cFPGAConfig.StopColumn, ".")
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

def fCapture():
    SPIBuf = bytearray(2)
    pixel=0
    pixel_num = []
    spectra = []
    fRegUpdate()
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
    spectraCount = len(spectra)
    for x in range(0, (spectraCount-1)):
        x0 = int((x/spectraCount)*920) + 40
        y0 = 540 - int(((spectra[x]-minvalue)/scale)*540)
        x1 = int(((x+1)/spectraCount)*920) + 40
        y1 = 540 - int(((spectra[x+1]-minvalue)/scale)*540)
        cSpectra.create_line(x0, y0, x1, y1, fill="green", width=1)

    root.after(1, fCapture)

        
FPGAConfig      = cFPGAConfig()

root = Tk()
root.title("SPI SIG")
frControl   = Frame(root)
frDraw      = Frame(root)

cbIntValidate   = root.register(fIntValidate)

strIntTime      = StringVar(frControl, str(FPGAConfig.IntTime))
lblIntTime      = Label(frControl, text = 'Integration Time').grid(row=0)
entIntTime      = Entry(frControl, textvariable = strIntTime, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entIntTime.grid(row=0, column=1)

strOffset       = StringVar(frControl, str(FPGAConfig.Offset))
lblOffset       = Label(frControl, text = 'CCD Offset').grid(row=1)
entOffset       = Entry(frControl, textvariable = strOffset, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entOffset.grid(row=1, column=1)

strGain         = StringVar(frControl, str(FPGAConfig.Gain))
lblGain         = Label(frControl, text = 'CCD Gain').grid(row=2)
entGain         = Entry(frControl, textvariable = strGain, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entGain.grid(row=2, column=1)

strStartLine    = StringVar(frControl, str(FPGAConfig.StartLine))
lblStartLine    = Label(frControl, text = 'Start Line').grid(row=3)
entStartLine    = Entry(frControl, textvariable = strStartLine, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entStartLine.grid(row=3, column=1)

strStopLine     = StringVar(frControl, str(FPGAConfig.StopLine))
lblStopLine     = Label(frControl, text = 'Stop Line').grid(row=4)
entStopLine     = Entry(frControl, textvariable = strStopLine, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entStopLine.grid(row=4, column=1)

strStartColumn  = StringVar(frControl, str(FPGAConfig.StartColumn))
lblStartColumn  = Label(frControl, text = 'Start Column').grid(row=5)
entStartColumn  = Entry(frControl, textvariable = strStartColumn, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entStartColumn.grid(row=5, column=1)

strStopColumn   = StringVar(frControl, str(FPGAConfig.StopColumn))
lblStopColumn   = Label(frControl, text = 'Stop Column').grid(row=6)
entStopColumn   = Entry(frControl, textvariable = strStopColumn, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
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

# Launch the GUI
frControl.grid(row=0, column=0)
frDraw.grid(row=0, column=1)
root.after(1, fCapture)
root.mainloop()
