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

eeprom_page = bytearray(64)
for i in eeprom_page:
    eeprom_page[i] = 0xFF

command = bytearray(7)

# Take control of the SPI Bus
while not spi.try_lock():
    pass

# Configure the SPI bus
spi.configure(baudrate=1000000, phase=0, polarity=0, bits=8)

# Fetch page 0 from the EEPROM
command = [0x3C, 0x00, 0x02, 0xB0, 0x40, 0xFF, 0x3E] 
spi.write(command, 0, 7)
# Wait for it to complete
#time.sleep(0.01)
## Read out the EEPROM buffer
#command = [0x3C, 0x00, 0x01, 0x31, 0xFF, 0x3E] 
#spi.write_readinto(command, eeprom_page, 0, 6, 0, 64)
#print(hex(eeprom_page[0]), hex(eeprom_page[1]), hex(eeprom_page[2]), hex(eeprom_page[3]), hex(eeprom_page[4]), hex(eeprom_page[5]), hex(eeprom_page[6]), hex(eeprom_page[7]))
#print(hex(eeprom_page[8]), hex(eeprom_page[9]), hex(eeprom_page[10]), hex(eeprom_page[11]), hex(eeprom_page[12]), hex(eeprom_page[13]), hex(eeprom_page[14]), hex(eeprom_page[15]))
#print(hex(eeprom_page[16]), hex(eeprom_page[17]), hex(eeprom_page[18]), hex(eeprom_page[19]), hex(eeprom_page[20]), hex(eeprom_page[21]), hex(eeprom_page[22]), hex(eeprom_page[23]))
#print(hex(eeprom_page[24]), hex(eeprom_page[25]), hex(eeprom_page[26]), hex(eeprom_page[27]), hex(eeprom_page[28]), hex(eeprom_page[29]), hex(eeprom_page[30]), hex(eeprom_page[31]))
#print(hex(eeprom_page[32]), hex(eeprom_page[33]), hex(eeprom_page[34]), hex(eeprom_page[35]), hex(eeprom_page[36]), hex(eeprom_page[37]), hex(eeprom_page[38]), hex(eeprom_page[39]))
#print(hex(eeprom_page[40]), hex(eeprom_page[41]), hex(eeprom_page[42]), hex(eeprom_page[43]), hex(eeprom_page[44]), hex(eeprom_page[45]), hex(eeprom_page[46]), hex(eeprom_page[47]))
#print(hex(eeprom_page[48]), hex(eeprom_page[49]), hex(eeprom_page[50]), hex(eeprom_page[51]), hex(eeprom_page[52]), hex(eeprom_page[53]), hex(eeprom_page[54]), hex(eeprom_page[55]))
#print(hex(eeprom_page[56]), hex(eeprom_page[57]), hex(eeprom_page[58]), hex(eeprom_page[59]), hex(eeprom_page[60]), hex(eeprom_page[61]), hex(eeprom_page[62]), hex(eeprom_page[63]))
#print()
#
## Fetch page 1 from the EEPROM
#command = [0x3C, 0x00, 0x02, 0xB0, 0x41, 0xFF, 0x3E] 
#spi.write(command, 0, 7)
## Wait for it to complete
#time.sleep(0.01)
## Read out the EEPROM buffer
#command = [0x3C, 0x00, 0x01, 0x31, 0xFF, 0x3E] 
#spi.write_readinto(command, eeprom_page, 0, 6, 0, 64)
#print(hex(eeprom_page[0]), hex(eeprom_page[1]), hex(eeprom_page[2]), hex(eeprom_page[3]), hex(eeprom_page[4]), hex(eeprom_page[5]), hex(eeprom_page[6]), hex(eeprom_page[7]))
#print(hex(eeprom_page[8]), hex(eeprom_page[9]), hex(eeprom_page[10]), hex(eeprom_page[11]), hex(eeprom_page[12]), hex(eeprom_page[13]), hex(eeprom_page[14]), hex(eeprom_page[15]))
#print(hex(eeprom_page[16]), hex(eeprom_page[17]), hex(eeprom_page[18]), hex(eeprom_page[19]), hex(eeprom_page[20]), hex(eeprom_page[21]), hex(eeprom_page[22]), hex(eeprom_page[23]))
#print(hex(eeprom_page[24]), hex(eeprom_page[25]), hex(eeprom_page[26]), hex(eeprom_page[27]), hex(eeprom_page[28]), hex(eeprom_page[29]), hex(eeprom_page[30]), hex(eeprom_page[31]))
#print(hex(eeprom_page[32]), hex(eeprom_page[33]), hex(eeprom_page[34]), hex(eeprom_page[35]), hex(eeprom_page[36]), hex(eeprom_page[37]), hex(eeprom_page[38]), hex(eeprom_page[39]))
#print(hex(eeprom_page[40]), hex(eeprom_page[41]), hex(eeprom_page[42]), hex(eeprom_page[43]), hex(eeprom_page[44]), hex(eeprom_page[45]), hex(eeprom_page[46]), hex(eeprom_page[47]))
#print(hex(eeprom_page[48]), hex(eeprom_page[49]), hex(eeprom_page[50]), hex(eeprom_page[51]), hex(eeprom_page[52]), hex(eeprom_page[53]), hex(eeprom_page[54]), hex(eeprom_page[55]))
#print(hex(eeprom_page[56]), hex(eeprom_page[57]), hex(eeprom_page[58]), hex(eeprom_page[59]), hex(eeprom_page[60]), hex(eeprom_page[61]), hex(eeprom_page[62]), hex(eeprom_page[63]))
#print()
#
## Fetch page 2 from the EEPROM
#command = [0x3C, 0x00, 0x02, 0xB0, 0x42, 0xFF, 0x3E] 
#spi.write(command, 0, 7)
## Wait for it to complete
#time.sleep(0.01)
## Read out the EEPROM buffer
#command = [0x3C, 0x00, 0x01, 0x31, 0xFF, 0x3E] 
#spi.write_readinto(command, eeprom_page, 0, 6, 0, 64)
#print(hex(eeprom_page[0]), hex(eeprom_page[1]), hex(eeprom_page[2]), hex(eeprom_page[3]), hex(eeprom_page[4]), hex(eeprom_page[5]), hex(eeprom_page[6]), hex(eeprom_page[7]))
#print(hex(eeprom_page[8]), hex(eeprom_page[9]), hex(eeprom_page[10]), hex(eeprom_page[11]), hex(eeprom_page[12]), hex(eeprom_page[13]), hex(eeprom_page[14]), hex(eeprom_page[15]))
#print(hex(eeprom_page[16]), hex(eeprom_page[17]), hex(eeprom_page[18]), hex(eeprom_page[19]), hex(eeprom_page[20]), hex(eeprom_page[21]), hex(eeprom_page[22]), hex(eeprom_page[23]))
#print(hex(eeprom_page[24]), hex(eeprom_page[25]), hex(eeprom_page[26]), hex(eeprom_page[27]), hex(eeprom_page[28]), hex(eeprom_page[29]), hex(eeprom_page[30]), hex(eeprom_page[31]))
#print(hex(eeprom_page[32]), hex(eeprom_page[33]), hex(eeprom_page[34]), hex(eeprom_page[35]), hex(eeprom_page[36]), hex(eeprom_page[37]), hex(eeprom_page[38]), hex(eeprom_page[39]))
#print(hex(eeprom_page[40]), hex(eeprom_page[41]), hex(eeprom_page[42]), hex(eeprom_page[43]), hex(eeprom_page[44]), hex(eeprom_page[45]), hex(eeprom_page[46]), hex(eeprom_page[47]))
#print(hex(eeprom_page[48]), hex(eeprom_page[49]), hex(eeprom_page[50]), hex(eeprom_page[51]), hex(eeprom_page[52]), hex(eeprom_page[53]), hex(eeprom_page[54]), hex(eeprom_page[55]))
#print(hex(eeprom_page[56]), hex(eeprom_page[57]), hex(eeprom_page[58]), hex(eeprom_page[59]), hex(eeprom_page[60]), hex(eeprom_page[61]), hex(eeprom_page[62]), hex(eeprom_page[63]))
#print()
#
## Fetch page 3 from the EEPROM
#command = [0x3C, 0x00, 0x02, 0xB0, 0x43, 0xFF, 0x3E] 
#spi.write(command, 0, 7)
## Wait for it to complete
#time.sleep(0.01)
## Read out the EEPROM buffer
#command = [0x3C, 0x00, 0x01, 0x31, 0xFF, 0x3E] 
#spi.write_readinto(command, eeprom_page, 0, 6, 0, 64)
#print(hex(eeprom_page[0]), hex(eeprom_page[1]), hex(eeprom_page[2]), hex(eeprom_page[3]), hex(eeprom_page[4]), hex(eeprom_page[5]), hex(eeprom_page[6]), hex(eeprom_page[7]))
#print(hex(eeprom_page[8]), hex(eeprom_page[9]), hex(eeprom_page[10]), hex(eeprom_page[11]), hex(eeprom_page[12]), hex(eeprom_page[13]), hex(eeprom_page[14]), hex(eeprom_page[15]))
#print(hex(eeprom_page[16]), hex(eeprom_page[17]), hex(eeprom_page[18]), hex(eeprom_page[19]), hex(eeprom_page[20]), hex(eeprom_page[21]), hex(eeprom_page[22]), hex(eeprom_page[23]))
#print(hex(eeprom_page[24]), hex(eeprom_page[25]), hex(eeprom_page[26]), hex(eeprom_page[27]), hex(eeprom_page[28]), hex(eeprom_page[29]), hex(eeprom_page[30]), hex(eeprom_page[31]))
#print(hex(eeprom_page[32]), hex(eeprom_page[33]), hex(eeprom_page[34]), hex(eeprom_page[35]), hex(eeprom_page[36]), hex(eeprom_page[37]), hex(eeprom_page[38]), hex(eeprom_page[39]))
#print(hex(eeprom_page[40]), hex(eeprom_page[41]), hex(eeprom_page[42]), hex(eeprom_page[43]), hex(eeprom_page[44]), hex(eeprom_page[45]), hex(eeprom_page[46]), hex(eeprom_page[47]))
#print(hex(eeprom_page[48]), hex(eeprom_page[49]), hex(eeprom_page[50]), hex(eeprom_page[51]), hex(eeprom_page[52]), hex(eeprom_page[53]), hex(eeprom_page[54]), hex(eeprom_page[55]))
#print(hex(eeprom_page[56]), hex(eeprom_page[57]), hex(eeprom_page[58]), hex(eeprom_page[59]), hex(eeprom_page[60]), hex(eeprom_page[61]), hex(eeprom_page[62]), hex(eeprom_page[63]))
#print()
#
## Fetch page 4 from the EEPROM
#command = [0x3C, 0x00, 0x02, 0xB0, 0x44, 0xFF, 0x3E] 
#spi.write(command, 0, 7)
## Wait for it to complete
#time.sleep(0.01)
## Read out the EEPROM buffer
#command = [0x3C, 0x00, 0x01, 0x31, 0xFF, 0x3E] 
#spi.write_readinto(command, eeprom_page, 0, 6, 0, 64)
#print(hex(eeprom_page[0]), hex(eeprom_page[1]), hex(eeprom_page[2]), hex(eeprom_page[3]), hex(eeprom_page[4]), hex(eeprom_page[5]), hex(eeprom_page[6]), hex(eeprom_page[7]))
#print(hex(eeprom_page[8]), hex(eeprom_page[9]), hex(eeprom_page[10]), hex(eeprom_page[11]), hex(eeprom_page[12]), hex(eeprom_page[13]), hex(eeprom_page[14]), hex(eeprom_page[15]))
#print(hex(eeprom_page[16]), hex(eeprom_page[17]), hex(eeprom_page[18]), hex(eeprom_page[19]), hex(eeprom_page[20]), hex(eeprom_page[21]), hex(eeprom_page[22]), hex(eeprom_page[23]))
#print(hex(eeprom_page[24]), hex(eeprom_page[25]), hex(eeprom_page[26]), hex(eeprom_page[27]), hex(eeprom_page[28]), hex(eeprom_page[29]), hex(eeprom_page[30]), hex(eeprom_page[31]))
#print(hex(eeprom_page[32]), hex(eeprom_page[33]), hex(eeprom_page[34]), hex(eeprom_page[35]), hex(eeprom_page[36]), hex(eeprom_page[37]), hex(eeprom_page[38]), hex(eeprom_page[39]))
#print(hex(eeprom_page[40]), hex(eeprom_page[41]), hex(eeprom_page[42]), hex(eeprom_page[43]), hex(eeprom_page[44]), hex(eeprom_page[45]), hex(eeprom_page[46]), hex(eeprom_page[47]))
#print(hex(eeprom_page[48]), hex(eeprom_page[49]), hex(eeprom_page[50]), hex(eeprom_page[51]), hex(eeprom_page[52]), hex(eeprom_page[53]), hex(eeprom_page[54]), hex(eeprom_page[55]))
#print(hex(eeprom_page[56]), hex(eeprom_page[57]), hex(eeprom_page[58]), hex(eeprom_page[59]), hex(eeprom_page[60]), hex(eeprom_page[61]), hex(eeprom_page[62]), hex(eeprom_page[63]))
#print()

# Release the SPI bus
spi.unlock

quit()
