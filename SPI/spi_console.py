import tkinter as tk
import tkinter.ttk as ttk

import time
import board
import digitalio
import busio

# Simple verification function for Integer inputs
def fIntValidate(input):
    if input.isdigit():
        return True                        
    elif input is "":
        return True
    else:
        return False

# Class for the revision register
class cCfgString:

    frame = None
    SPI   = None

    def __init__(self, name, row, value, address):
        self.value       = str(value)
        self.address    = int(address)
        self.label      = tk.Label(cCfgString.frame, text = name)
        self.label.grid(row=row, column=0)
        self.stringVar  = tk.StringVar(cCfgString.frame, str(value))
        self.entry      = tk.Entry(cCfgString.frame, textvariable=self.stringVar, width = 5)
        self.entry.grid(row=row, column=1)

    # Read a string from the FPGA. This is only used for the revision register
    def SPIRead(self):
        command  = bytearray(5)
        response = bytearray(12)
        command = [0x3C, 0x00, 0x01, self.address, 0x3E]
        cCfgString.SPI.write_readinto(command, response, 0, 5, 0, 12)
        # Decode the binary response into a string
        self.value = response[5:11].decode()
        # Set the text in the entry box
        self.stringVar.set(self.value)

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

    # Init class defines the objects name, default value, and FPGA Address
    # Creates a label and entry for the item.
    def __init__(self, name, row, value, address):
        self.name       = name
        self.value      = int(value)
        self.address    = int(address)
        self.label      = tk.Label(cCfgEntry.frame, text = name)
        self.label.grid(row=row, column=0)
        self.stringVar  = tk.StringVar(cCfgEntry.frame, str(value))
        self.entry      = tk.Entry(cCfgEntry.frame, textvariable=self.stringVar, validate="key", validatecommand=(cCfgEntry.validate, '%S'), width = 5)
        self.entry.grid(row=row, column=1)
            
    # Read a 16 bit integer from the FPGA. Used for everything else
    def SPIRead(self):
        command  = bytearray(5)
        response = bytearray(7)
        # A read command consists of opening and closing delimeters, the payload size (typically only 1 for the command byte),
        # and the command/address.
        # Refer to ENG-150 for additional information
        command  = [0x3C, 0x00, 0x01, self.address, 0x3E, 0x00, 0x00, 0x00]
        SPI.write_readinto(command, response, 0, 5, 0, 7)
        self.value = (response[6] << 8) + response[5]
        self.stringValue.set(str(self.value))

    def SPIWrite(self):
        command = bytearray(8)
        # Convert the int into bytes.
        txData = bytearray(2)
        txData[1]   = self.value >> 8
        txData[0]   = self.value - (txData[1] << 8)
        # A write command consists of opening and closing delimeters, the payload size which is data + 1 (for the command byte),
        # the command/address with the MSB set for a write operation, the payload data, and the CRC. This function does not 
        # caluculate the CRC nor read back the status.
        # Refer to ENG-150 for additional information
        command = [0x3C, 0x00, 0x03, (self.address+0x80), txData[0], txData[1], 0xFF, 0x3E]
        SPI.write(command, 0, 8)

    # Fetch the data from the entry box and update it to the FPGA
    def Update(self):
        if self.value != int(self.stringVar.get()):
            self.value = int(self.stringVar.get())
            self.SPIWrite()
# End Class cCfgEntry

# Class container for the two combo boxes
class cCfgCombo:

    # Static class variables used for comms
    frame       = None
    SPI         = None

    # Init class defines the objects name, default value, and FPGA Address
    # Creates a label for the item.
    def __init__(self, row):
        self.value      = 3
        self.address    = 0x2B
        self.row        = row
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
            
    # Read a 16 bit integer from the FPGA. Used for everything else
    def SPIRead(self):
        command  = bytearray(5)
        response = bytearray(7)
        command  = [0x3C, 0x00, 0x01, self.address, 0x3E]
        SPI.write_readinto(command, response, 0, 5, 0, 7)
        self.value = (response[6] << 8) + response[5]
        self.stringValue.set(str(self.value))

    def SPIWrite(self):
        command = bytearray(7)
        command = [0x3C, 0x00, 0x02, (self.address+0x80), self.value, 0xFF, 0x3E]
        SPI.write(command, 0, 7)

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

# EEPROM Control Window Class
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

    def EEPROMRead(self):
        EEPROMPage  = bytearray(68)
        command     = bytearray(7)
        page        = int(self.pageStr.get())
        command     = [0x3C, 0x00, 0x02, 0xB0, (0x40 + page), 0xFF, 0x3E]
        self.SPI.write(command, 0, 7)
        time.sleep(0.01)
        command = [0x3C, 0x00, 0x01, 0x31, 0xFF, 0x3E]
        self.SPI.write_readinto(command, EEPROMPage, 0, 6, 0, 68)
        for x in range(0, 64):
            self.valStrings[x].set(str(hex(EEPROMPage[x+4])))

    def EEPROMWrite(self):
        page        = int(entEEPROMPage.get())
        command     = bytearray(7)
        EEPROMWrCmd = bytearray(70)
        EEPROMWrCmd[0:3] = [0x3C, 0x00, 0x41, 0xB1]
        for x in range(0, 64):
            EEPROMWrCmd[x+4] = int(slef.valStrings[x].get(), 16)

        EEPROMWrCmd[68] = 0xFF
        EEPROMWrCmd[69] = 0x3E
        self.SPI.write(EEPROMWrCmd, 0, 70)
        command = [0x3C, 0x00, 0x02, 0xB0, (0x80 + page), 0xFF, 0x3E]
        self.SPI.write(command, 0, 7)
# End Class cWinEEPROM

# Class container for the main window and all of its elements
class cWinMain:

    def __init__(self, SPI, ready, trigger, intValidate):
        # Register the handles
        self.SPI        = SPI
        self.ready      = ready
        self.trigger    = trigger
        # Create and title a window
        self.root = tk.Tk()
        self.root.title("SPI SIG")
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
        self.canvas = tk.Canvas(self.drawFrame, bg="black", height=540, width=960)
        self.canvas.pack()
        self.drawFrame.grid(row=0, column=1)
        # Empty list for the config objects
        self.configObjects = []
        # Create an object for the FPGA Revision
        self.configObjects.append(cCfgString("FPGA Revision", 0, "00.0.00", 0x10))
        # Special case, we want this box read only
        self.configObjects[0].entry.config(state='disabled', disabledbackground='light grey', disabledforeground='black')
        # Create all of the config entries        
        self.configObjects.append(cCfgEntry("Integration Time" , 1 , 100   , 0x11))
        self.configObjects.append(cCfgEntry("Detector Offset"  , 2 , 0     , 0x13))
        self.configObjects.append(cCfgEntry("Detector Gain"    , 3 , 0x100 , 0x14))
        self.configObjects.append(cCfgEntry("Start Line"       , 4 , 250   , 0x50))
        self.configObjects.append(cCfgEntry("Stop Line"        , 5 , 750   , 0x51))
        self.configObjects.append(cCfgEntry("Start Column"     , 6 , 500   , 0x52))
        self.configObjects.append(cCfgEntry("Stop Column"      , 7 , 1500  , 0x53))
        # Add the AD/OD combo boxes
        self.configObjects.append(cCfgCombo(8))
        # Add the buttons
        self.btnCapture = tk.Button(self.configFrame, text='Update', command=self.FPGAUpdate)
        self.btnCapture.grid(row=10, column=0)
        self.btnEEPROM  = tk.Button(self.configFrame, text='EEPROM', command=self.openEEPROM)
        self.btnEEPROM.grid(row=10, column=1)
        # Resize the grid
        col_count, row_count = self.configFrame.grid_size()
        self.configFrame.grid_columnconfigure(0, minsize=110)
        self.configFrame.grid_columnconfigure(1, minsize=100)
        for row in range(row_count):
            self.configFrame.grid_rowconfigure(row, minsize=30)
        # Write the initial values
        self.FPGAInit()
        # Launch the main loop
        self.root.after(10, self.Acquire)
        self.root.mainloop()

    def Acquire(self):
        SPIBuf  = bytearray(2)
        spectra = []
        # Send and acquire trigger
        self.trigger.value = True

        # Wait until the data is ready
        while not self.ready.value:
            pass

        # Relase the trigger
        self.trigger.value = False

        # Read in the spectra
        while self.ready.value:
            self.SPI.readinto(SPIBuf, 0, 2)
            pixel = (SPIBuf[0] << 8) + SPIBuf[1]
            spectra.append(pixel)

        maxvalue = 0
        minvalue = 65536
        spectraBinned = []
        for x in range(1, len(spectra), 2):
            pixel = int((spectra[x-1] + spectra[x]) / 2)
            if pixel > maxvalue:
                maxvalue = pixel
            if pixel < minvalue:
                minvalue = pixel
            spectraBinned.append(pixel)

        # Draw the graph
        scale = maxvalue - minvalue
        if scale != 0:
            midvalue = int(minvalue + (scale/2))
            self.canvas.delete("all")
            self.canvas.create_text(20,20,text=str(maxvalue), fill="white")
            self.canvas.create_text(20,270,text=str(midvalue), fill="white")
            self.canvas.create_text(20,520,text=str(minvalue), fill="white")
            spectraCount = len(spectraBinned)
            for x in range(1, spectraCount):
                x0 = int((x/spectraCount)*920) + 40
                y0 = 520 - int(((spectraBinned[(x-1)]-minvalue)/scale)*500)
                x1 = int(((x+1)/spectraCount)*920) + 40
                y1 = 520 - int(((spectraBinned[x]-minvalue)/scale)*500)
                self.canvas.create_line(x0, y0, x1, y1, fill="green", width=1)
        self.root.after(10, self.Acquire)

    def FPGAInit(self):
        response = bytearray(2)
        # Read out an errant data
        while self.ready.value:
            self.SPI.readinto(response, 0, 2)
        # Fetch the revision from the FPGA
        self.configObjects[0].SPIRead()
        # Iterate through each of the config objects and write to the FPGA
        for x in range(1, len(self.configObjects)):
            self.configObjects[x].SPIWrite()

    def FPGAUpdate(self):
        response = bytearray(2)
        # Read out an errant data
        while self.ready.value:
            self.SPI.readinto(response, 0, 2)
        # Iterate through each of the config objects and update to the FPGA if necessary
        for cfgObj in self.configObjects:
            cfgObj.Update()

    def openEEPROM(self):
        self.winEEPROM = cWinEEPROM(self.SPI, self.cbIntValidate)
# End Class cWinMain

###############Begin Main################
# Initialize the SPI bus on the FT232H
SPI  = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# Initialize D5 as the ready signal
ready = digitalio.DigitalInOut(board.D5)
ready.direction = digitalio.Direction.INPUT

# Initialize D6 as the trigger
trigger = digitalio.DigitalInOut(board.D6)
trigger.direction = digitalio.Direction.OUTPUT
trigger.value = False

# Take control of the SPI Bus
while not SPI.try_lock():
    pass

# Configure the SPI bus
SPI.configure(baudrate=8000000, phase=0, polarity=0, bits=8)

# Create the main window and pass in the handles
winSIG = cWinMain(SPI, ready, trigger, fIntValidate)
