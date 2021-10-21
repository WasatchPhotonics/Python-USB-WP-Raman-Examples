from tkinter import *
from tkinter.ttk import *
from matplotlib import pyplot

import time
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
    StartColumn = 12
    StopColumn  = 1932

def fWriteIntTime():
    command     = bytearray(7)
    response    = bytearray(7)
    #Clear any garbage
    while ready.value:
        spi.readinto(response, 0, 2)
    command     = [0x3c, 0x00, 0x02, 0x91, cFPGAConfig.IntTime, 0xFF, 0x3E]
    print("Writing integration time of ", cFPGAConfig.IntTime, "ms.")
    print(hex(command[0]), hex(command[1]), hex(command[2]), hex(command[3]), hex(command[4]), hex(command[5]), hex(command[6]))
    spi.write(command, 0, 7)
    print("Reading back integration time.")
    command = [0x3C, 0x00, 0x01, 0x11, 0x3E, 0x00]
    spi.write_readinto(command, response, 0, 7, 0, 7)
    print(hex(response[0]), hex(response[1]), hex(response[2]), hex(response[3]), hex(response[4]), hex(response[5]), hex(response[6]))
 
def fWriteOffset():
    command     = bytearray(7)
    response    = bytearray(7)
    while ready.value:
        spi.readinto(response, 0, 2)
    command     = [0x3c, 0x00, 0x02, 0x93, cFPGAConfig.Offset, 0xFF, 0x3E]
    print("Writing offset of ", cFPGAConfig.Offset, ".")
    print(command)
    spi.write(command, 0, 7)
    print("Reading offset.")
    command = [0x3C, 0x00, 0x01, 0x13, 0x3E, 0x00]
    spi.write_readinto(command, response, 0, 7, 0, 7)
    print(response[4])
 
def fWriteGain():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    command     = [0x3c, 0x00, 0x03, 0x94, 0x00, cFPGAConfig.Gain, 0xFF, 0x3E]
    print("Writing gain of ", cFPGAConfig.Gain, "dB.")
    print(command)
    spi.write(command, 0, 7)
    print("Reading back gain.")
    command = [0x3C, 0x00, 0x01, 0x14, 0x3E, 0x00, 0x00]
    spi.write_readinto(command, response, 0, 8, 0, 8)
    print(response[5])
 
def fWriteStartLine():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StartLine0  = int(cFPGAConfig.StartLine % 256)
    StartLine1  = int(cFPGAConfig.StartLine / 256)
    command     = [0x3c, 0x00, 0x03, 0xD0, StartLine0, StartLine1, 0xFF, 0x3E]
    print("Writing start line of ", cFPGAConfig.StartLine, ".")
    print(command)
    spi.write(command, 0, 7)
    print("Reading back start line.")
    command = [0x3C, 0x00, 0x01, 0x50, 0x3E, 0x00, 0x00]
    spi.write_readinto(command, response, 0, 8, 0, 8)
    StartLine = (response[5] * 256) + response[4]
    print(StartLine)
 
def fWriteStopLine():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StopLine0   = int(cFPGAConfig.StopLine % 256)
    StopLine1   = int(cFPGAConfig.StopLine / 256)
    command     = [0x3c, 0x00, 0x03, 0xD1, StopLine0, StopLine1, 0xFF, 0x3E]
    print("Writing stop line of ", cFPGAConfig.StopLine, ".")
    print(command)
    spi.write(command, 0, 7)
    print("Reading back stop line.")
    command = [0x3C, 0x00, 0x01, 0x51, 0x3E, 0x00, 0x00]
    spi.write_readinto(command, response, 0, 8, 0, 8)
    StopLine = (response[5] * 256) + response[4]
    print(StopLine)
 
def fWriteStartColumn():
    command         = bytearray(8)
    response        = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StartColumn0    = int(cFPGAConfig.StartColumn % 256)
    StartColumn1    = int(cFPGAConfig.StartColumn / 256)
    command         = [0x3c, 0x00, 0x03, 0xD2, StartColumn0, StartColumn1, 0xFF, 0x3E]
    print("Writing start column of ", cFPGAConfig.StartColumn, ".")
    print(command)
    spi.write(command, 0, 7)
    print("Reading back start column.")
    command = [0x3C, 0x00, 0x01, 0x52, 0x3E, 0x00, 0x00]
    spi.write_readinto(command, response, 0, 8, 0, 8)
    StartColumn = (response[5] * 256) + response[4]
    print(StartColumn)
 
def fWriteStopColumn():
    command     = bytearray(8)
    response    = bytearray(8)
    while ready.value:
        spi.readinto(response, 0, 2)
    StopColumn0 = int(cFPGAConfig.StopColumn % 256)
    StopColumn1 = int(cFPGAConfig.StopColumn / 256)
    command     = [0x3c, 0x00, 0x03, 0xD0, StopColumn0, StopColumn1, 0xFF, 0x3E]
    print("Writing start line of ", cFPGAConfig.StopColumn, ".")
    print(command)
    spi.write(command, 0, 7)
    print("Reading back start line.")
    command = [0x3C, 0x00, 0x01, 0x50, 0x3E, 0x00, 0x00]
    spi.write_readinto(command, response, 0, 8, 0, 8)
    StopColumn = (response[5] * 256) + response[4]
    print(StopColumn)
 
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

def fCapture():
    SPIBuf = bytearray(2)
    pixel=0
    pixel_num = []
    spectra = []
    fRegUpdate()
    print("Capturing")
    # Send and acquire trigger
    trigger.value = True

    # Wait until the data is ready
    while not ready.value:
        pass

    print("Data Ready")
    # Relase the trigger
    trigger.value = False

    # Read in the spectra
    while ready.value:
        spi.readinto(SPIBuf, 0, 2)
        pixel = (SPIBuf[0] * 256) + SPIBuf[1]
        spectra.append(pixel)

    print("Data Read")
    for x in range(FPGAConfig.StartColumn, (FPGAConfig.StartColumn+len(spectra))):
        pixel_num.append(x)

    pyplot.plot(pixel_num,spectra)

    pyplot.xlabel('Pixel')
    pyplot.ylabel('Count')
    pyplot.title('SIG Capture')
    pyplot.show()

        
FPGAConfig      = cFPGAConfig()

root = Tk()
root.title("SPI SIG")
cbIntValidate   = root.register(fIntValidate)

strIntTime      = StringVar(root, str(FPGAConfig.IntTime))
lblIntTime      = Label(root, text = 'Integration Time').grid(row=0)
entIntTime      = Entry(root, textvariable = strIntTime, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entIntTime.grid(row=0, column=1)

strOffset       = StringVar(root, str(FPGAConfig.Offset))
lblOffset       = Label(root, text = 'CCD Offset').grid(row=1)
entOffset       = Entry(root, textvariable = strOffset, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entOffset.grid(row=1, column=1)

strGain         = StringVar(root, str(FPGAConfig.Gain))
lblGain         = Label(root, text = 'CCD Gain').grid(row=2)
entGain         = Entry(root, textvariable = strGain, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entGain.grid(row=2, column=1)

strStartLine    = StringVar(root, str(FPGAConfig.StartLine))
lblStartLine    = Label(root, text = 'Start Line').grid(row=3)
entStartLine    = Entry(root, textvariable = strStartLine, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entStartLine.grid(row=3, column=1)

strStopLine     = StringVar(root, str(FPGAConfig.StopLine))
lblStopLine     = Label(root, text = 'Stop Line').grid(row=4)
entStopLine     = Entry(root, textvariable = strStopLine, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entStopLine.grid(row=4, column=1)

strStartColumn  = StringVar(root, str(FPGAConfig.StartColumn))
lblStartColumn  = Label(root, text = 'Start Column').grid(row=5)
entStartColumn  = Entry(root, textvariable = strStartColumn, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entStartColumn.grid(row=5, column=1)

strStopColumn   = StringVar(root, str(FPGAConfig.StopColumn))
lblStopColumn   = Label(root, text = 'Stop Column').grid(row=6)
entStopColumn   = Entry(root, textvariable = strStopColumn, validate="key", validatecommand=(cbIntValidate, '%P'), width = 5)
entStopColumn.grid(row=6, column=1)

strADBitWidth   = StringVar(root)
lblADBitWidth   = Label(root, text = 'AD Bit Width').grid(row=7)
entADBitWidth   = Combobox(root, textvariable = strADBitWidth, width = 4)
entADBitWidth.grid(row=7, column=1)
entADBitWidth['values'] = ('10', '12')
entADBitWidth['state']  = 'readonly'
entADBitWidth.current(1)

strODBitWidth   = StringVar(root)
lblODBitWidth   = Label(root, text = 'OD Bit Width').grid(row=8)
entODBitWidth   = Combobox(root, textvariable = strODBitWidth, width = 4)
entODBitWidth.grid(row=8, column=1)
entODBitWidth['values'] = ('10', '12')
entODBitWidth['state']  = 'readonly'
entODBitWidth.current(1)

btnCapture      = Button(root, text='Capture', command=fCapture)
btnCapture.grid(row=10)

col_count, row_count = root.grid_size()

root.grid_columnconfigure(0, minsize=110)
root.grid_columnconfigure(1, minsize=100)

for row in range(row_count):
    root.grid_rowconfigure(row, minsize=30)

# Take control of the SPI Bus
while not spi.try_lock():
    pass

# Configure the SPI bus
spi.configure(baudrate=1000000, phase=0, polarity=0, bits=8)

# Write initial config
fWriteIntTime()
fWriteOffset()
fWriteGain()
fWriteStartLine()
fWriteStopLine()
#fWriteStartColumn()
#fWriteStopColumn()

# Launch the GUI
mainloop()
