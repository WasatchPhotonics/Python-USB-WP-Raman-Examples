import datetime
import optparse
import os
import sys

#Documentation by Nico
#Script by Robert Dickerson
c          = 0		# This will control how many bytes of bin data per line of the .c file
iBlockSize = 16384  # This doesn't seem to do anything since it doesn't appear agian in the program, but the number does.
bError     = False  # Flag to show when there is an error with the arguments.
bFirstLine = True


parser = optparse.OptionParser(version='%prog 1.0')
parser.add_option('-f', dest='FpgaBinFile', help='FPGA Bin File')
parser.add_option('-c', dest='COutputFile', help='C Output File')
parser.add_option('-i', dest='HOutputFile', help='Header Output File')

if len(sys.argv) <= 1:
	parser.print_help()
	sys.exit()
	
(options, args) = parser.parse_args()

if options.FpgaBinFile is None:
	print('ERROR: Need to Specify FPGA Bin File (-f)')
	bError = True
	
if options.COutputFile is None:
	print('ERROR: Need to Specify C Output File (-c)')
	bError = True
	
if options.HOutputFile is None:
	print('ERROR: Need to Specify Header Output File (-h)')
	bError = True
	
if bError:
	sys.exit(2)
	
if not os.path.exists(options.FpgaBinFile):
	print('ERROR: Could Not Find FPGA Bin File - ' + options.FpgaBinFile)
	sys.exit(2)
	
print('################################################################################')
print('# FPGA Converter from BIN to C')
print('################################################################################')
print('\tFPGA Bin File = ' + options.FpgaBinFile)
print('\tC Output File = ' + options.COutputFile)
print('################################################################################')
   
   
try:
	cof = open(options.COutputFile, 'w')
except:
	print('ERROR: ', sys.exc_info()[0], '\n\t', sys.exc_info()[1])
	sys.exit(2)
   
   
cof.write('/* FPGA Converter from BIN to C\n')
cof.write('   Input File:   ' + options.FpgaBinFile + '\n')
cof.write('   Generated On: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' */\n\n')
cof.write('#include <stdint.h>\n\n')
cof.write('const uint8_t FPGAData[] = {\n')


try:
	fb = open(options.FpgaBinFile, 'rb')	
except:
	print('ERROR: ', sys.exc_info()[0], '\n\t', sys.exc_info()[1])
	sys.exit(2)
	

block = fb.read(16384)

while len(block) > 0:
	sOutput = []
	
	for b in block:			
		if type(b) is str:
			bn = int('{:08b}'.format(ord(b))[::-1],2)
		elif type(b) is int:
			bn = int('{:08b}'.format(b)[::-1],2)	
			
		sOutput.append('0x' + format(ord(chr(bn)), 'x').zfill(2))
		c += 1
		
		if c >= 16:
			if not bFirstLine:
				cof.write(',\n')
			else:
				bFirstLine = False
				
			cof.write('\t' + ', '.join(sOutput))
			sOutput = []
			c       = 0
	
	if c > 0:
		cof.write(',\n\t' + ', '.join(sOutput))
		
	block = fb.read(16384)
	
cof.write('\n};\n\n')
   
try:
	hof = open(options.HOutputFile, 'w')
except:
	print('ERROR: ', sys.exc_info()[0], '\n\t', sys.exc_info()[1])
	sys.exit(2)
	
hof.write('/* FPGA Converter from BIN to C\n')
hof.write('   Input File:   ' + options.FpgaBinFile + '\n')
hof.write('   Generated On: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' */\n\n')
hof.write('#ifndef FPGA_DATA_H\n')
hof.write('#define FPGA_DATA_H\n\n')
hof.write('#include <stdint.h>\n\n')
hof.write('#define FPGA_PROGRAM_SIZE ' + str(os.path.getsize(options.FpgaBinFile)) +
          '\t\t// size of Spartan-6 FPGA ' + str(os.path.getsize(options.FpgaBinFile)) + 
	       ' bytes\n')
hof.write('const uint8_t FPGAData[FPGA_PROGRAM_SIZE];\n\n')
hof.write('#endif //FPGA_DATA_H\n')


fb.close()
cof.close()
hof.close()
