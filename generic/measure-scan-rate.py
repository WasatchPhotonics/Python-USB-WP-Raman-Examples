import os
import re
import sys
import struct
import usb.core
import argparse
from datetime import datetime
from dataclasses import dataclass

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS     = 1000 

@dataclass
class Result:
    integration_time_ms: int
    max_elapsed_ms: int
    elapsed_sec: float
    scan_rate: float            # spectra/sec
    measurement_rate: float     # ms/spectrum
    integration_total_sec: float
    comms_total_sec: float
    comms_average_ms: float

class Fixture(object):

    ############################################################################
    # Lifecycle 
    ############################################################################

    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--keep-trying",         action="store_true", help="ignore timeouts")
        parser.add_argument("--integration-time-ms", type=int,            help="integration time (ms)", default=100)
        parser.add_argument("--count",               type=int,            help="read the given number of spectra", default=10)
        parser.add_argument("--pid",                 type=str,            help="desired PID (e.g. 4000)")
        parser.add_argument("--outfile",             type=str,            help="CSV filename")
        parser.add_argument("--profile-ms",          type=str,            help="list of of integration times (e.g. 2000,1000,500,250,100,50,10,5,1)")
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

        if os.name == "posix":
            self.device.set_configuration(1)
            usb.util.claim_interface(self.device, 0)

        self.read_eeprom()
        self.fw_version = self.get_firmware_version()
        self.fpga_version = self.get_fpga_version()
        self.results = []
        self.last_integ = None

        print("connected to %s %s (%d-pixel %s) (%.2f, %.2fnm) (FW %s, FPGA %s)" % (
            self.model, self.serial_number, 
            self.pixels, self.detector,
            self.wavelengths[0], self.wavelengths[-1], 
            self.fw_version, self.fpga_version))

    ############################################################################
    # methods
    ############################################################################

    def run(self):
        if self.args.profile_ms is not None:
            int_times = [ int(x) for x in self.args.profile_ms.split(",") ]
            print(f"Profiling scan rate for the following integration times: {int_times}")
            for ms in int_times:
                print("-"*50)
                self.profile_integration_time(ms)
        else:
            self.profile_integration_time(self.args.integration_time_ms)

        if self.args.outfile:
            self.save_csv()

    def profile_integration_time(self, ms):
        print(f"Reading {self.args.count} spectra at {ms}ms")

        # apply integration time, then take two throwaways to be sure
        self.send_cmd(0xb2, ms)
        for i in range(2):
            self.get_spectrum(ms)

        last_total = 0
        start = datetime.now()
        max_elapsed_ms = -1
        for i in range(self.args.count):
            
            this_start = datetime.now()
            spectrum = self.get_spectrum(ms)
            this_elapsed_ms = (datetime.now() - this_start).total_seconds() * 1000.0
            max_elapsed_ms = max(max_elapsed_ms, this_elapsed_ms)

            # make sure we're really reading distinct spectra
            total = sum(spectrum)
            print(f"{datetime.now()}: spectrum {i+1} (sum {total})")

            if total == last_total:
                print("Warning: consecutive spectra summed to %d" % total)
            last_total = total

        end = datetime.now()
        max_elapsed_ms = int(round(max_elapsed_ms, 0))

        # record observed time
        elapsed_sec = (end - start).total_seconds()
        scan_rate = float(self.args.count) / elapsed_sec
        measurement_rate = 1000.0 / scan_rate

        # compare vs theoretical time
        integration_total_sec = self.args.count * ms * 0.001
        comms_total_sec = elapsed_sec - integration_total_sec
        comms_average_ms = (comms_total_sec / self.args.count) * 1000.0

        print("")
        print(f"read {self.args.count} spectra at {ms} ms in {elapsed_sec:.2f} sec\n")
        print(f"max elapsed             = {max_elapsed_ms} ms")
        print(f"measurement rate        = {measurement_rate:6.2f} ms/spectrum")
        print(f"scan rate               = {scan_rate:6.2f} spectra/sec")
        print(f"cumulative integration  = {integration_total_sec:6.2f} sec")
        print(f"cumulative latency      = {comms_total_sec:6.2f} sec")
        print(f"average latency         = {comms_average_ms:6.2f} ms/spectrum")

        r = Result(integration_time_ms  = ms,
                   elapsed_sec          = elapsed_sec,
                   max_elapsed_ms       = max_elapsed_ms,
                   scan_rate            = scan_rate,
                   measurement_rate     = measurement_rate,
                   integration_total_sec= integration_total_sec,
                   comms_total_sec      = comms_total_sec,
                   comms_average_ms     = comms_average_ms)
        self.results.append(r)

    def save_csv(self):
        with open(self.args.outfile, "w") as outfile:
            outfile.write(f"Spectra, Integration Time (ms), Elapsed Sec, Max Elapsed (ms), Measurement Rate (ms/spectrum), Scan Rate (spectra/sec), Cumulative Integration Sec, Cumulative Latency Sec, Average Latency (ms/spectrum)\n")
            for r in self.results:
                outfile.write(f"{self.args.count}, {r.integration_time_ms}, {r.elapsed_sec}, {r.max_elapsed_ms}, {r.measurement_rate}, {r.scan_rate}, {r.integration_total_sec}, {r.comms_total_sec}, {r.comms_average_ms}\n")

    def read_eeprom(self):
        self.buffers = [self.get_cmd(0xff, 0x01, page) for page in range(8)]

        # parse key fields (extend as needed)
        self.format          = self.unpack((0, 63,  1), "B")
        self.model           = self.unpack((0,  0, 16), "s")
        self.serial_number   = self.unpack((0, 16, 16), "s")
        self.detector        = self.unpack((2,  0, 16), "s")
        self.pixels          = self.unpack((2, 16,  2), "H")

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

    def get_spectrum(self, ms):
        timeout_ms = TIMEOUT_MS + ms * 10
        if self.last_integ is not None:
            timeout_ms += self.last_integ * 10

        # send trigger
        self.send_cmd(0xad)

        bytes_to_read = self.pixels * 2
        data = []
        while True:
            try:
                this_data = self.device.read(0x82, bytes_to_read, timeout=timeout_ms)
                data.extend(this_data)
                if len(data) >= bytes_to_read:
                    break
            except usb.core.USBTimeoutError as ex:
                if not self.args.keep_trying:
                    raise 

        self.last_integ = ms

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
