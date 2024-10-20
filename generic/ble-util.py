import matplotlib.pyplot as plt
import numpy as np
import argparse
import asyncio
import struct
import re

from time import sleep
from bleak import BleakScanner, BleakClient
from datetime import datetime

import EEPROMFields

class Fixture:
    WASATCH_SERVICE   = "D1A7FF00-AF78-4449-A34F-4DA1AFAF51BC"
    DISCOVERY_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"

    ############################################################################
    # Lifecycle
    ############################################################################

    def __init__(self):

        self.stop_event = asyncio.Event()

        self.client = None
        self.found = False
        self.eeprom = None
        self.eeprom_field_loc = EEPROMFields.get_eeprom_fields()
        self.integration_time_ms = 0 # read from EEPROM startup field

        self.code_by_name = { "INTEGRATION_TIME_MS": 0xff01, 
                              "GAIN_DB":             0xff02,
                              "LASER_STATE":         0xff03,
                              "ACQUIRE_SPECTRUM":    0xff04,
                              "SPECTRUM_CMD":        0xff05,
                              "READ_SPECTRUM":       0xff06,
                              "EEPROM_CMD":          0xff07,
                              "EEPROM_DATA":         0xff08,
                              "BATTERY_STATUS":      0xff09,
                              "GENERIC":             0xff0a }

        self.generics = { "SET_GAIN_DB":                 0xb7,
                          "GET_GAIN_DB":                 0xc5,
                          "SET_INTEGRATION_TIME_MS":     0xb2,
                          "GET_INTEGRATION_TIME_MS":     0xbf,
                          "GET_LASER_WARNING_DELAY_SEC": 0x8b,
                          "SET_LASER_WARNING_DELAY_SEC": 0x8a,
                          "NEXT_TIER":                   0xff,
                                                         
                          "SET_START_LINE":              0x21,
                          "SET_STOP_LINE":               0x23,
                          "GET_AMBIENT_TEMPERATURE":     0x2a,
                          "GET_POWER_WATCHDOG_SEC":      0x31,
                          "SET_POWER_WATCHDOG_SEC":      0x30,
                          "SET_SCANS_TO_AVERAGE":        0x62,
                          "GET_SCANS_TO_AVERAGE":        0x63 }

        # reverse lookups
        self.name_by_uuid = { self.wrap_uuid(code): name for name, code in self.code_by_name.items() }
        self.generic_by_code = { code: name for name, code in self.generics.items() }

        self.parse_args()

    def parse_args(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        group = parser.add_argument_group('Discovery')
        group.add_argument("--debug",                   action="store_true", help="debug output")
        group.add_argument("--search-timeout-sec",      type=int,            help="how long to search for spectrometers", default=30)
        group.add_argument("--serial-number",           type=str,            help="delay n ms between spectra")
        group.add_argument("--eeprom",                  action="store_true", help="display EEPROM and exit")
        group.add_argument("--monitor",                 action="store_true", help="monitor battery, laser state etc\n")

        group = parser.add_argument_group('Spectra')
        group.add_argument("--spectra",                 type=int,            help="spectra to acquire", default=5)
        group.add_argument("--auto-dark",               action="store_true", help="take Auto-Dark measurements")
        group.add_argument("--auto-raman",              action="store_true", help="take Auto-Raman measurements\n")
        group.add_argument("--outfile",                 type=str,            help="save spectra to CSV file")
        group.add_argument("--plot",                    action="store_true", help="graph spectra")
                                                         
        group = parser.add_argument_group('Acquisition Parameters')
        group.add_argument("--integration-time-ms",     type=int,            help="set integration time")
        group.add_argument("--gain-db",                 type=float,          help="set gain (dB)")
        group.add_argument("--scans-to-average",        type=int,            help="set scan averaging", default=1)
        group.add_argument("--laser-enable",            action="store_true", help="fire the laser")
        group.add_argument("--start-line",              type=int,            help="set vertical ROI start line")
        group.add_argument("--stop-line",               type=int,            help="set vertical ROI stop line\n")

        group = parser.add_argument_group('Ramping')
        group.add_argument("--ramp-integ",              action="store_true", help="ramp integration time")
        group.add_argument("--ramp-gain",               action="store_true", help="ramp gain dB")
        group.add_argument("--ramp-avg",                action="store_true", help="ramp scan averaging")
        group.add_argument("--ramp-roi",                action="store_true", help="ramp vertical roi")
        group.add_argument("--ramp-repeats",            type=int,            help="spectra at each ramp step", default=5)

        group = parser.add_argument_group('Timing')
        group.add_argument("--laser-warning-delay-sec", type=int,            help="set laser warning delay (sec)")
        group.add_argument("--power-watchdog-sec",      type=int,            help="set power watchdog (sec)")

        self.args = parser.parse_args()

    async def run(self):

        # note: will not connect to 'random' or first-found device, for laser safety reasons
        if self.args.serial_number:
            print(f"Searching for {self.args.serial_number}...")
        else:
            print(f"No serial number specified, so will list search results and exit after {self.args.search_timeout_sec}sec.\n")

        # connect to device, read device information and characteristics
        await self.connect()
        if not self.client:
            return

        # always read EEPROM (needed to read spectra)
        await self.read_eeprom()
        if self.args.eeprom:
            self.display_eeprom()
            return

        # timeouts
        if self.args.power_watchdog_sec is not None:
            await self.set_power_watchdog_sec(self.args.power_watchdog_sec)
        if self.args.laser_warning_delay_sec is not None:
            await self.set_laser_warning_delay_sec(self.args.laser_warning_delay_sec)

        # explicit laser control
        if self.args.laser_enable:
            await self.set_laser_enable(True)

        # apply acquisition parameters
        if self.args.integration_time_ms is not None:
            await self.set_integration_time_ms(self.args.integration_time_ms)
        if self.args.gain_db is not None:
            await self.set_gain_db(self.args.gain_db)
        if self.args.scans_to_average is not None:
            await self.set_scans_to_average(self.args.scans_to_average)
        if self.args.start_line is not None:
            await self.set_start_line(self.args.start_line)
        if self.args.stop_line is not None:
            await self.set_stop_line(self.args.stop_line)

        # take spectra or monitor
        if self.args.monitor:
            await self.monitor()
        elif self.args.spectra:
            await self.perform_collection()

        # explicit laser control
        if self.args.laser_enable:
            await self.set_laser_enable(False)

    ############################################################################
    # BLE Connection
    ############################################################################

    async def connect(self):
        self.start_time = datetime.now()

        print(f"{datetime.now()} rssi local_name")
        async with BleakScanner(detection_callback=self.detection_callback, service_uuids=[self.WASATCH_SERVICE]) as scanner:
            await self.stop_event.wait()

        # scanner stops when block exits
        self.debug("scanner stopped")

        if self.client is None:
            if self.args.serial_number:
                print(f"{self.args.serial_number} not found")
            return

        # connect 
        await self.client.connect()

        # grab device information
        await self.load_device_information()

        # get Characteristic information
        await self.load_characteristics()

        elapsed_sec = (datetime.now() - self.start_time).total_seconds()
        self.debug(f"initial connection took {elapsed_sec:.2f} sec")

    def detection_callback(self, device, advertisement_data):
        """
        discovered device 13874014-5EDA-5E6B-220E-605D00FE86DF: WP-SiG:WP-01791, 
        advertisement_data AdvertisementData(local_name='WP-SiG:WP-01791', 
                                             service_uuids=['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc'], 
                                             tx_power=0, rssi=-67)
        """
        if self.found:
            return

        if (datetime.now() - self.start_time).total_seconds() >= self.args.search_timeout_sec:
            self.debug("timeout expired")
            self.stop_scanning()
            return

        self.debug(f"discovered device {device}, advertisement_data {advertisement_data}")
        if not self.is_xs(device):
            return

        print(f"{datetime.now()} {advertisement_data.rssi:4d} {advertisement_data.local_name}")
        if self.args.serial_number is None:
            return # we're just listing

        if self.args.serial_number.lower() not in advertisement_data.local_name.lower():
            return # not the one

        self.debug("stopping scanner")
        self.found = True

        if self.args.debug:
            self.dump(device, advertisement_data)

        self.debug("instantiating BleakClient")
        self.client = BleakClient(address_or_ble_device=device, 
                                  disconnected_callback=self.disconnected_callback,
                                  timeout=self.args.search_timeout_sec)
        self.stop_event.set()
        self.debug(f"BleakClient instantiated: {self.client}")

    def stop_scanning(self):
        self.stop_event.set()

    def disconnected_callback(self):
        print("\ndisconnected")

    async def load_device_information(self):
        self.debug(f"address {self.client.address}")
        self.debug(f"mtu_size {self.client.mtu_size} bytes")

        self.device_info = {}
        for service in self.client.services:
            if "Device Information" in str(service):
                for char in service.characteristics:
                    name = char.description
                    value = self.decode(await self.client.read_gatt_char(char.uuid))
                    self.device_info[name] = value

        self.debug("Device Information:")
        for k, v in self.device_info.items():
            self.debug(f"  {k:30s} {v}")

    async def load_characteristics(self):
        # find the primary service
        self.primary_service = None
        for service in self.client.services:
            if service.uuid.lower() == self.WASATCH_SERVICE.lower():
                self.primary_service = service
                
        if self.primary_service is None:
            return

        # iterate over standard Characteristics
        # @see https://bleak.readthedocs.io/en/latest/api/client.html#gatt-characteristics
        self.debug("Characteristics:")
        for char in self.primary_service.characteristics:
            name = self.get_name_by_uuid(char.uuid)
            extra = ""

            if "write-without-response" in char.properties:
                extra += f", Max write w/o rsp size: {char.max_write_without_response_size}"

            props = ",".join(char.properties)
            self.debug(f"  {name:30s} {char.uuid} ({props}){extra}")

    async def read_char(self, name, min_len=None, quiet=False):
        uuid = self.get_uuid_by_name(name)
        if uuid is None:
            raise RuntimeError(f"invalid characteristic {name}")

        response = await self.client.read_gatt_char(uuid)
        if response is None:
            # responses may be optional on a write, but they're required on read
            raise RuntimeError("attempt to read {name} returned no data")

        if not quiet:
            self.debug(f"<< read_char({name}, min_len {min_len}): {response}")
            if min_len is not None and len(response) < min_len:
                self.debug(f"WARNING: characteristic {name} returned insufficient data ({len(response)} < {min_len})")

        buf = bytearray()
        for byte in response:
            buf.append(byte)
        return buf

    async def write_char(self, name, data, quiet=False):
        """
        Although write_gatt_char takes a 'response' flag, that is used to request
        an ACK for purpose of delivery verification; BLE writes don't ever 
        generate a "data" response.
        """
        uuid = self.get_uuid_by_name(name)
        if uuid is None:
            raise RuntimeError(f"invalid characteristic {name}")

        if isinstance(data, list):
            self.debug(f"data was {data}")
            data = bytearray(data)
            self.debug(f"data now {data}")
        extra = self.expand_path(name, data)

        if not quiet:
            self.debug(f">> write_char({name}, {data}){extra}")
        await self.client.write_gatt_char(uuid, data, response=True) # ack all writes

    def expand_path(self, name, data):
        if name != "GENERIC":
            return ""
        path = []
        for i in range(len(data)):
            code = data[i]
            name = self.generic_by_code[code]
            path.append(name)
            if code != 0xff:
                break
        return " [" + ", ".join(path) + "]"

    ############################################################################
    # Timeouts
    ############################################################################

    async def set_power_watchdog_sec(self, sec):
        tier = self.generics.get("NEXT_TIER")
        cmd = self.generics.get("SET_POWER_WATCHDOG_SEC")
        await self.write_char("GENERIC", [tier, cmd, sec])

    async def set_laser_warning_delay_sec(self, sec):
        cmd = self.generics.get("SET_LASER_WARNING_DELAY_SEC")
        await self.write_char("GENERIC", [cmd, sec])

    ############################################################################
    # Laser Control
    ############################################################################

    async def set_laser_enable(self, flag):
        data = [ 0xff,                   # mode (no change)
                 0xff,                   # type (no change)
                 0x01 if flag else 0x00, # laser enable
                 0xff ]                  # laser watchdog (no change)
               # 0xffff                  # reserved
               # 0xff                    # status mask
        await self.write_char("LASER_STATE", data)

    ############################################################################
    # Acquisition Parameters
    ############################################################################

    async def set_integration_time_ms(self, ms):
        # using dedicated Characteristic, although 2nd-tier version now exists
        print(f"setting integration time to {ms}ms")
        data = [ 0x00,               # fixed
                 (ms << 16) & 0xff,  # MSB
                 (ms <<  8) & 0xff,
                 (ms      ) & 0xff ] # LSB
        await self.write_char("INTEGRATION_TIME_MS", data)
        self.integration_time_ms = ms

    async def set_gain_db(self, db):
        # using dedicated Characteristic, although 2nd-tier version now exists
        print(f"setting gain to {db}dB")
        msb = int(db) & 0xff
        lsb = int((db - int(db)) * 256) & 0xff
        await self.write_char("GAIN_DB", [msb, lsb])

    async def set_scans_to_average(self, n):
        print(f"setting scan averaging to {n}")
        tier = self.generics.get("NEXT_TIER")
        cmd = self.generics.get("SET_SCANS_TO_AVERAGE")
        await self.write_char("GENERIC", [tier, cmd, n])

    async def set_start_line(self, n):
        print(f"setting start line to {n}")
        tier = self.generics.get("NEXT_TIER")
        cmd = self.generics.get("SET_START_LINE")
        await self.write_char("GENERIC", [tier, cmd, n])

    async def set_stop_line(self, n):
        print(f"setting stop line to {n}")
        tier = self.generics.get("NEXT_TIER")
        cmd = self.generics.get("SET_STOP_LINE")
        await self.write_char("GENERIC", [tier, cmd, n])

    async def set_vertical_roi(self, pair):
        await self.set_start_line(pair[0])
        await self.set_stop_line (pair[1])

    ############################################################################
    # Monitor
    ############################################################################

    async def get_battery_state(self):
        buf = await self.read_char("BATTERY_STATUS", 2)
        self.debug(f"battery response: {buf}")
        return { 'charging': buf[0] != 0,
                 'perc': int(buf[1]) }

    async def get_laser_state(self):
        retval = {}
        for k in [ 'mode', 'type', 'enable', 'watchdog_sec', 'mask', 'interlock_closed', 'laser_firing' ]:
            retval[k] = None
            
        buf = await self.read_char("LASER_STATE", 7)
        if len(buf) >= 4:
            retval.update({
                'mode':            buf[0],
                'type':            buf[1],
                'enable':          buf[2],
                'watchdog_sec':    buf[3] })

        if len(buf) >= 7: 
            retval.update({
                'mask':            buf[6],
                'interlock_closed':buf[6] & 0x01,
                'laser_firing':    buf[6] & 0x02 })

        return retval

    async def get_status(self):
        bat = await self.get_battery_state()
        bat_perc = f"{bat['perc']:3d}%"
        bat_chg = 'charging' if bat['charging'] else 'discharging'

        las = await self.get_laser_state()
        las_firing = las['laser_firing']
        intlock = 'closed (armed)' if las['interlock_closed'] else 'open (safe)'

        return f"Battery {bat_perc} ({bat_chg}), Laser {las_firing}, Interlock {intlock}"

    async def monitor(self):
        print("\nPress ctrl-C to exit...\n")
        while True:
            try:
                status = await self.get_status()
                print(f"{datetime.now()} {status}")
                sleep(1)
            except KeyboardInterrupt:
                print()
                break

    ############################################################################
    # Ramps
    ############################################################################

    def init_ramps(self):
        self.ramped_integ = None
        self.ramped_gain = None
        self.ramped_avg = None
        self.ramped_roi = None
        self.ramping = False

        n = self.args.spectra

        if self.args.ramp_integ:
            step = 2000 // (n-1)
            self.ramping = True
            self.ramped_integ = [ max(10, i*step) for i in range(n) ]
            print(f"ramping integration time: {self.ramped_integ}")

        if self.args.ramp_gain:
            step = round(30 / (n-1), 1)
            self.ramping = True
            self.ramped_gain = [ i*step for i in range(n) ]
            print(f"ramping gain dB: {self.ramped_gain}")

        if self.args.ramp_avg:
            self.ramping = True
            self.ramped_avg = [ 1, 5, 25, 125, 255 ]
            print(f"ramping scan averaging: {self.ramped_avg}")

        if self.args.ramp_roi:
            self.ramping = True
            step = 1080 // n
            self.ramped_roi = [ (i*n, (i+1)*n) for i in range(n) ]
            print(f"ramping vertical ROI: {self.ramped_roi}")

    async def update_ramps(self, i):
        if self.ramped_integ: 
            await self.set_integration_time_ms(self.ramped_integ[i])

        if self.ramped_gain:  
            await self.set_gain_db(self.ramped_gain[i])

        if self.ramped_roi:   
            await self.set_vertical_roi(self.ramped_roi[i])

        if self.ramped_avg:
            if i < len(self.ramped_avg):
                await self.set_scans_to_average(self.ramped_avg[i])

    ############################################################################
    # Spectra
    ############################################################################

    async def perform_collection(self):
        # init outfile
        if self.args.outfile:
            with open(self.args.outfile, "a") as outfile:
                outfile.write(f"pixel, " + ", ".join([f"{v}" for v in range(self.pixels)]) + "\n")
                outfile.write(f"wavelengths, " + ", ".join([f"{v:.2f}" for v in self.wavelengths]) + "\n")
                if self.wavenumbers:
                    outfile.write(f"wavenumbers, " + ", ".join([f"{v:.2f}" for v in self.wavenumbers]) + "\n")

        # init graph
        if self.args.plot:
            xaxis = self.wavenumbers if self.wavenumbers else self.wavelengths
            plt.ion()

        # init ramps
        self.init_ramps()

        # collect however many spectra were requested
        count = 0
        for step in range(self.args.spectra):
            await self.update_ramps(step)

            repeats = self.args.ramp_repeats if self.ramping else 1
            for repeat in range(repeats):
                count += 1
                start_time = datetime.now()
                spectrum = await self.get_spectrum()
                now = datetime.now()
                elapsed_ms = int(round((now - start_time).total_seconds() * 1000, 0))

                hi = max(spectrum)
                avg = sum(spectrum) / len(spectrum)
                std = np.std(spectrum)

                print(f"{now} received spectrum {step:3d}/{self.args.spectra} (elapsed {elapsed_ms:5d}ms, max {hi:8.2f}, avg {avg:8.2f}, std {std:8.2f}) {spectrum[:10]}")

                if self.args.outfile:
                    with open(self.args.outfile, "a") as outfile:
                        outfile.write(f"{now}, " + ", ".join([str(v) for v in spectrum]) + "\n")
                        
                if self.args.plot:
                    if not self.ramping:
                        plt.clf()
                    plt.plot(xaxis, spectrum)
                    plt.draw()
                    plt.pause(0.01)

    async def get_spectrum(self):
        header_len = 2 # the 2-byte first_pixel
        pixels_read = 0
        spectrum = [0] * self.pixels

        # determine which type of measurement
        if self.args.auto_raman: 
            arg = 2
        elif self.args.auto_dark: 
            arg = 1
        else: 
            arg = 0

        # send the ACQUIRE
        await self.write_char("ACQUIRE_SPECTRUM", [arg], quiet=True)

        # compute timeout
        timeout_ms = self.integration_time_ms * self.args.scans_to_average + 6000 # 4sec latency + 2sec buffer
        start_time = datetime.now()

        # read the spectral data
        while pixels_read < self.pixels:
            if (datetime.now() - start_time).total_seconds() * 1000 > timeout_ms:
                raise RuntimeError(f"failed to read spectrum within timeout {timeout_ms}ms")

            # self.debug(f"requesting spectrum packet starting at pixel {pixels_read}")
            data = pixels_read.to_bytes(2, byteorder="big")
            await self.write_char("SPECTRUM_CMD", data, quiet=True)

            # self.debug(f"reading spectrum data (hopefully from pixels_read {pixels_read})")
            response = await self.read_char("READ_SPECTRUM", quiet=True)

            # validate spectrum response
            response_len = len(response)
            if (response_len < header_len or response_len % 2 != 0):
                raise RuntimeError(f"received invalid READ_SPECTRUM response of {response_len} bytes")

            # first_pixel is a big-endian uint16
            first_pixel = int((response[0] << 8) | response[1])
            if first_pixel != pixels_read:
                # self.debug(f"received NACK (first_pixel {first_pixel})")
                sleep(0.2)
                continue
            
            pixels_in_packet = int((response_len - header_len) / 2)
            self# .debug(f"received spectrum packet starting at pixel {first_pixel} with {pixels_in_packet} pixels")

            for i in range(pixels_in_packet):
                # pixel intensities are little-endian uint16
                offset = header_len + i * 2
                intensity = int((response[offset+1] << 8) | response[offset])

                spectrum[pixels_read] = intensity
                pixels_read += 1

                if pixels_read == self.pixels:
                    # self.debug("read complete spectrum")
                    if (i + 1 != pixels_in_packet):
                        raise RuntimeError(f"ERROR: ignoring {pixels_in_packet - (i + 1)} trailing pixels")

        return spectrum

    ############################################################################
    # EEPROM
    ############################################################################

    async def read_eeprom(self):
        await self.read_eeprom_pages()
        self.parse_eeprom_pages()
        self.generate_wavecal()

        # grab initial integration time (used for acquisition timeout)
        self.integration_time_ms = self.eeprom["startup_integration_time_ms"]

        msg  = f"Connected to {self.eeprom['model']} {self.eeprom['serial_number']} with {self.pixels} pixels "
        msg += f"from ({self.wavelengths[0]:.2f}, {self.wavelengths[-1]:.2f}nm)"
        if self.wavenumbers:
            msg += f" ({self.wavenumbers[0]:.2f}, {self.wavenumbers[-1]:.2f}cm⁻¹)"
        print(f"{datetime.now()} {msg}")

    def display_eeprom(self):
        print("EEPROM:")
        for name, value in self.eeprom.items():
            print(f"  {name:30s} {value}")

    def generate_wavecal(self):
        self.pixels = self.eeprom["active_pixels_horizontal"]
        coeffs = [ self.eeprom[f"wavecal_c{i}"] for i in range(5) ]

        self.wavelengths = []
        for i in range(self.pixels):
            nm = (  coeffs[0] +
                  + coeffs[1] * i
                  + coeffs[2] * i * i
                  + coeffs[3] * i * i * i
                  + coeffs[4] * i * i * i * i)
            self.wavelengths.append(nm)

        self.excitation = self.eeprom["excitation_nm_float"]
        self.wavenumbers = None
        if self.excitation:
            self.wavenumbers = [ (1e7/self.excitation - 1e7/nm) for nm in self.wavelengths ]

    async def read_eeprom_pages(self):
        start_time = datetime.now()

        self.eeprom = {}
        self.pages = []

        cmd_uuid = self.get_uuid_by_name("EEPROM_CMD")
        data_uuid = self.get_uuid_by_name("EEPROM_DATA")
        for page in range(8):
            buf = bytearray()
            for subpage in range(4):
                await self.write_char("EEPROM_CMD", [page, subpage], quiet=True)
                #await self.client.write_gatt_char(cmd_uuid, page_ids, response = True)

                response = await self.read_char("EEPROM_DATA", quiet=True)
                #response = await self.client.read_gatt_char(data_uuid)
                for byte in response:
                    buf.append(byte)
            self.pages.append(buf)

        elapsed_sec = (datetime.now() - start_time).total_seconds()
        self.debug(f"reading eeprom took {elapsed_sec:.2f} sec")

    def parse_eeprom_pages(self):
        for name, field in self.eeprom_field_loc.items():
            self.unpack_eeprom_field(field.pos, field.data_type, name)

    def unpack_eeprom_field(self, address, data_type, field):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        if page > len(self.pages):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (field %s)" % ( 
                page, start_byte, length, data_type, field))
            return

        buf = self.pages[page]
        if buf is None or end_byte > len(buf):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: buf is %s (field %s)" % ( 
                page, start_byte, length, data_type, buf, field))
            return

        if data_type == "s":
            unpack_result = ""
            for c in buf[start_byte:end_byte]:
                if c == 0:
                    break
                unpack_result += chr(c)
        else:
            unpack_result = 0 
            try:
                unpack_result = struct.unpack(data_type, buf[start_byte:end_byte])[0]
            except Exception as ex:
                print("error unpacking EEPROM page %d, offset %d, len %d as %s (field %s): %s" % (page, start_byte, length, data_type, field, ex))
                return

        # self.debug(f"Unpacked page {page:02d}, offset {start_byte:02d}, len {length:02d}, datatype {data_type}: {unpack_result} {field}")
        self.eeprom[field] = unpack_result

    ############################################################################
    # Utility
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print(f"{datetime.now()} DEBUG: {msg}")

    def wrap_uuid(self, code):
        return f"d1a7{code:04x}-af78-4449-a34f-4da1afaf51bc".lower()

    def get_name_by_uuid(self, uuid):
        return self.name_by_uuid.get(uuid.lower(), None)
        
    def get_uuid_by_name(self, name):
        code = self.code_by_name.get(name.upper(), None)
        if code is None:
            return
        return self.wrap_uuid(code)

    def dump(self, device, advertisement_data):
        self.debug("==> Device:")
        for attr in ['name', 'address', 'details']:
            if hasattr(device, attr):
                value = getattr(device, attr)
                self.debug(f"  {attr} = {value}")
        self.debug("==> Advertising Data:")
        for attr in ['local_name', 'manufacturer_data', 'platform_data', 'rssi', 'service_data', 'service_uuids', 'tx_power']:
            if hasattr(advertisement_data, attr):
                value = getattr(advertisement_data, attr)
                self.debug(f"  {attr} = {value}")

    def is_xs(self, device, advertisement_data=None):
        if device is None:
            return
        elif advertisement_data is not None:
            return self.WASATCH_SERVICE.lower() in advertisement_data.service_uuids
        else:
            return "wp-" in device.name.lower()

    def decode(self, data):
        try:
            if isinstance(data, bytearray):
                return data.decode('utf-8')
        except:
            pass
        return data

if __name__ == "__main__":
    fixture = Fixture()
    asyncio.run(fixture.run())
