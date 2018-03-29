import usb.core
import datetime
from time import sleep

dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000)

print dev
HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

class FPGAOptions(object):

    def __init__(self, word):
        # bits 0-2: 0000 0000 0000 0111 IntegrationTimeResolution
        # bit  3-5: 0000 0000 0011 1000 DataHeader
        # bit    6: 0000 0000 0100 0000 HasCFSelect
        # bit  7-8: 0000 0001 1000 0000 LaserType
        # bit 9-11: 0000 1110 0000 0000 LaserControl
        # bit   12: 0001 0000 0000 0000 HasAreaScan
        # bit   13: 0010 0000 0000 0000 HasActualIntegTime
        # bit   14: 0100 0000 0000 0000 HasHorizBinning

        self.integration_time_resolution = (word & 0x0007)
        self.data_header                 = (word & 0x0038) >> 3
        self.has_cf_select               = (word & 0x0040) != 0
        self.laser_type                  = (word & 0x0180) >> 7
        self.laser_control               = (word & 0x0e00) >> 9
        self.has_area_scan               = (word & 0x1000) != 0
        self.has_actual_integ_time       = (word & 0x2000) != 0
        self.has_horiz_binning           = (word & 0x4000) != 0

        self.dump()

    def dump(self):
        print("FPGA Compilation Options:")
        print("  integration time resolution = %s" % self.stringify_resolution())
        print("  data header                 = %s" % self.stringify_header())
        print("  has cf select               = %s" % self.has_cf_select)
        print("  laser type                  = %s" % self.stringify_laser_type())
        print("  laser control               = %s" % self.stringify_laser_control())
        print("  has area scan               = %s" % self.has_area_scan)
        print("  has actual integ time       = %s" % self.has_actual_integ_time)
        print("  has horiz binning           = %s" % self.has_horiz_binning)

    def stringify_resolution(self):
        v = self.integration_time_resolution
        return "1ms" if v == 0 else "10ms" if v == 1 else "switchable" if v == 2 else "unknown"

    def stringify_header(self):
        v = self.data_header
        return "none" if v == 0 else "ocean" if v == 1 else "wasatch" if v == 2 else "unknown"

    def stringify_laser_type(self):
        v = self.laser_type
        return "none" if v == 0 else "internal" if v == 1 else "external" if v == 2 else "unknown"

    def stringify_laser_control(self):
        v = self.laser_control
        return "modulation" if v == 0 else "transition" if v == 1 else "ramping" if v == 2 else "unknown"

# Note: the following seems to violate the PyUSB documentation:
# 
# "The first four parameters are the bmRequestType, bmRequest, wValue and wIndex 
#  fields of the standard control transfer structure. The fifth parameter is 
#  either the data payload for an OUT transfer or the number of bytes to read in 
#  an IN transfer."
#  https://github.com/pyusb/pyusb/blob/master/docs/tutorial.rst#talk-to-me-honey
# 
# The 5th parameter in the following code is clearly sending a data payload 
# buffer rather than an integral count of expected bytes, even though it is
# clearly an IN transfer.  Note that in other DEVICE_TO_HOST transfers (see
# GetModelConfig.py), an expected integral count is correctly sent.

fake_buf = [0] * 8    # bReqType        bReq  wValue  wIndex  buf/cnt   timeout
buf = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x0004, 0x0000, fake_buf, TIMEOUT_MS)
word = buf[0] | (buf[1] << 8)

print("FPGA Compilation Options: 0x%04x" % word)
options = FPGAOptions(word)
