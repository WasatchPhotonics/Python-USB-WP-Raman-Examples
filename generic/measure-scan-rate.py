import re
import sys
import struct
import usb.core
import argparse
from datetime import datetime

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000 

class Fixture(object):

    ############################################################################
    # Lifecycle 
    ############################################################################

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms)", default=100)
        parser.add_argument("--count",               type=int,            help="read the given number of spectra", default=10)
        parser.add_argument("--pid",                 type=str,            help="desired PID (e.g. 4000)")
        self.args = parser.parse_args()

        self.device = None
        for pid in [0x1000, 0x2000, 0x4000]:
            self.debug("looking for PID 0x%04x" % pid)
            if self.device:
                break

            if self.args.pid is not None:
                if pid != int(self.args.pid, 16):
                    continue

            for dev in usb.core.find(find_all=True, idVendor=0x24aa, idProduct=pid):
                self.debug("looking at %s" % dev)
                self.device = dev
                break

        if self.device is None:
            return

        self.device.set_configuration(1)
        usb.util.claim_interface(self.device, 0)

        self.read_eeprom()
        self.fw_version = self.get_firmware_version()
        self.fpga_version = self.get_fpga_version()

        print("connected to %s %s (%d-pixel %s) (%.2f, %.2fnm) (FW %s, FPGA %s)" % (
            self.model, self.serial_number, 
            self.pixels, self.detector,
            self.wavelengths[0], self.wavelengths[-1], 
            self.fw_version, self.fpga_version))

    ############################################################################
    # methods
    ############################################################################

    def run(self):
        # set integration time
        self.send_cmd(0xb2, self.args.integration_time_ms)

        last_total = 0
        start = datetime.now()
        for i in range(self.args.count):
            spectrum = self.get_spectrum()

            # make sure we're really reading distinct spectra
            total = sum(spectrum)
            if total == last_total:
                print("Warning: consecutive spectra summed to %d" % total)
            last_total = total

            # if i != 0 and (i % 100 == 0 or i + 1 == self.args.count):
            #     print("%s read %d spectra" % (datetime.now(), i + 1))

        end = datetime.now()

        # measure observed time
        elapsed_sec = (end - start).total_seconds()
        scan_rate = float(self.args.count) / elapsed_sec

        # compare vs theoretical time
        integration_total_sec = self.args.count * self.args.integration_time_ms * 0.001
        comms_total_sec = elapsed_sec - integration_total_sec
        comms_average_ms = (comms_total_sec / self.args.count) * 1000.0

        print("")
        print("read %d spectra at %d ms in %.2f sec\n" % (self.args.count, self.args.integration_time_ms, elapsed_sec))
        print("effective measurement rate = %6.2f ms/spectrum at %dms integration time" % (1000.0 / scan_rate, self.args.integration_time_ms))
        print("effective scan rate        = %6.2f spectra/sec at %dms integration time" % (scan_rate, self.args.integration_time_ms))
        print("")
        print("cumulative integration     = %6.2f sec over %d measurements" % (integration_total_sec, self.args.count))
        print("cumulative overhead        = %6.2f sec over %d measurements" % (comms_total_sec, self.args.count))
        print("effective comms latency    = %6.2f ms/spectrum" % comms_average_ms)

    def read_eeprom(self):
        self.buffers = [self.get_cmd(0xff, 0x01, page) for page in range(8)]

        # parse key fields (extend as needed)
        self.format          = self.unpack((0, 63,  1), "B")
        self.model           = self.unpack((0,  0, 16), "s")
        self.serial_number   = self.unpack((0, 16, 16), "s")
        self.detector        = self.unpack((2,  0, 16), "s")
        self.pixels          = self.unpack((2, 25,  2), "H" if self.format >= 4 else "h")

        self.wavelength_coeffs = [0] * 5
        for i in range(4):
            self.wavelength_coeffs[i] = self.unpack((1,  i * 4,  4), "f")
        if self.format > 7:
            self.wavelength_coeffs[4] = self.unpack((2, 21,  4), "f")

        self.wavelengths = [0] * self.pixels
        for i in range(self.pixels):
            self.wavelengths[i] = self.wavelength_coeffs[0] \
                                + self.wavelength_coeffs[1] * i \
                                + self.wavelength_coeffs[2] * i * i \
                                + self.wavelength_coeffs[3] * i * i * i \
                                + self.wavelength_coeffs[4] * i * i * i * i

    def get_firmware_version(self):
        result = self.get_cmd(0xc0)
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self):
        s = ""
        result = self.get_cmd(0xb4)
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
                    s += chr(c)
        return s

    def set_integration_time_ms(self, n):
        if n < 1 or n > 0xffff:
            print("ERROR: script only supports uint16 integration time")
            return
        self.send_cmd(0xb2, n)

    def get_spectrum(self):
        timeout_ms = TIMEOUT_MS + self.args.integration_time_ms * 2
        self.send_cmd(0xad, 1)
        data = self.device.read(0x82, self.pixels * 2, timeout=timeout_ms)
        spectrum = []
        for i in range(0, len(data), 2):
            spectrum.append(data[i] | (data[i+1] << 8))
        return spectrum

    ############################################################################
    # utility 
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print("DEBUG: %s" % msg)

    def send_cmd(self, cmd, value=0, index=0, buf=None):
        if buf is None:
            if self.device.idProduct == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s" % (HOST_TO_DEVICE, cmd, value, index, buf))
        self.device.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64):
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d)" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS))
        result = self.device.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        self.debug("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) << %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, result))
        return result

    def unpack(self, address, data_type):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        buf = self.buffers[page]
        if buf is None or end_byte > len(buf):
            raise("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (label %s)" %
                (page, start_byte, length, data_type, buf, label))

        if data_type == "s":
            result = ""
            for c in buf[start_byte:end_byte]:
                if c == 0:
                    break
                result += chr(c)
        else:
            result = struct.unpack(data_type, buf[start_byte:end_byte])[0]
        return result

################################################################################
# main()
################################################################################

fixture = Fixture()
if fixture.device is None:
    print("No spectrometers found")
    sys.exit(0)
fixture.run()
