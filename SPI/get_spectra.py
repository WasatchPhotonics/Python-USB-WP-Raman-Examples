import board
import digitalio
import busio

spi  = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

ready = digitalio.DigitalInOut(board.D5)
ready.direction = digitalio.Direction.INPUT

trigger = digitalio.DigitalInOut(board.D6)
trigger.direction = digitalio.Direction.OUTPUT
trigger.value = False

spectra = bytearray(2)
command = bytearray(8)

# Take control of the SPI Bus
while not spi.try_lock():
    pass

# Configure the SPI bus
spi.configure(baudrate=1000000, phase=0, polarity=0, bits=8)

# Set the start line to 250
command = [0x3C, 0x00, 0x02, 0xD0, 0xFA, 0x00, 0xFF, 0x3E] 
spi.write(command, 0, 8)

# Set the stop line to 750
command = [0x3C, 0x00, 0x02, 0xD1, 0xEE, 0x02, 0xFF, 0x3E] 
spi.write(command, 0, 8)

# Send and acquire trigger
trigger.value = True

# Wait until the data is ready
while not ready.value:
    pass

# Relase the trigger
trigger.value = False

# Read in the spectra
while ready.value:
    spi.readinto(spectra, 0, 2)
    print(((spectra[0] * 256) + spectra[1]))

# Release the SPI bus
spi.unlock

quit()
