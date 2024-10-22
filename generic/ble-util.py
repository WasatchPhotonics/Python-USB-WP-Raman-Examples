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
    """
    Known issues:
        - advertisement_data.local_name seems cropped to 10char ("WP-XS:WP-0") on 
          Windows (bleak.backends.winrt), making connection by serial number 
          impossible?

        - enable notifications on:
          ?READ_SPECTRUM       (read,write,indicate)
          ?EEPROM_DATA         (read,indicate)
          ?GENERIC             (read,write,indicate)
    """
    VERSION = "1.0.3"

    WASATCH_SERVICE   = "D1A7FF00-AF78-4449-A34F-4DA1AFAF51BC"
    DISCOVERY_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"

    LASER_TEC_MODES = ['OFF', 'ON', 'AUTO', 'AUTO_ON']
    ACQUIRE_ERRORS = ['NONE', 'BATT_SOC_INFO_NOT_RCVD', 'BATT_SOC_TOO_LOW', 'LASER_DIS_FLR', 'LASER_ENA_FLR', 
                      'IMG_SNSR_IN_BAD_STATE', 'IMG_SNSR_STATE_TRANS_FLR', 'SPEC_ACQ_SIG_WAIT_TMO', 'UNKNOWN']

    ############################################################################
    # Lifecycle
    ############################################################################

    def __init__(self):

        self.stop_event = asyncio.Event()

        self.client = None
        self.keep_scanning = True
        self.eeprom = None
        self.eeprom_field_loc = EEPROMFields.get_eeprom_fields()
        self.integration_time_ms = 0 # read from EEPROM startup field
        self.last_integration_time_ms = 2000
        self.last_spectrum_received = None
        self.laser_enable = False
        self.laser_warning_delay_sec = 3

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

        self.generics = { "SET_GAIN_DB":                 0xb7, # first-tier
                          "GET_GAIN_DB":                 0xc5,
                          "SET_INTEGRATION_TIME_MS":     0xb2,
                          "GET_INTEGRATION_TIME_MS":     0xbf,
                          "GET_LASER_WARNING_DELAY_SEC": 0x8b,
                          "SET_LASER_WARNING_DELAY_SEC": 0x8a,
                          "SET_LASER_TEC_MODE":          0x84,
                          "NEXT_TIER":                   0xff,
                                                         
                          "SET_START_LINE":              0x21, # second-tier
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
        parser = argparse.ArgumentParser(
            description="Command-line utility for testing and characterizing BLE spectrometers",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",                  action="store_true", help="debug output")

        group = parser.add_argument_group('Discovery')
        group.add_argument("--serial-number",           type=str,            help="auto-connect on discovery")
        group.add_argument("--first",                   action="store_true", help="connect to first-discovered 'WP-XS' device (required for Windows?)")
        group.add_argument("--eeprom",                  action="store_true", help="display EEPROM and exit")
        group.add_argument("--monitor",                 action="store_true", help="monitor battery, laser state etc")
        group.add_argument("--notifications",           action="store_true", help="enable notifications")
        group.add_argument("--search-timeout-sec",      type=int,            help="how long to search for spectrometers", default=30)

        group = parser.add_argument_group('Spectra')
        group.add_argument("--spectra",                 type=int,            help="number of spectra to acquire", default=5)
        group.add_argument("--auto-dark",               action="store_true", help="take Auto-Dark measurements")
        group.add_argument("--auto-raman",              action="store_true", help="take Auto-Raman measurements")
        group.add_argument("--outfile",                 type=str,            help="save spectra to CSV file")
        group.add_argument("--plot",                    action="store_true", help="graph spectra")
        group.add_argument("--overlay",                 action="store_true", help="overlay spectra on graph")
                                                         
        group = parser.add_argument_group('Acquisition Parameters')
        group.add_argument("--integration-time-ms",     type=int,            help="set integration time")
        group.add_argument("--gain-db",                 type=float,          help="set gain (dB)")
        group.add_argument("--scans-to-average",        type=int,            help="set scan averaging")
        group.add_argument("--start-line",              type=int,            help="set vertical ROI start line")
        group.add_argument("--stop-line",               type=int,            help="set vertical ROI stop line")

        group = parser.add_argument_group('Laser Control')
        group.add_argument("--laser-enable",            action="store_true", help="fire the laser (disables laser watchdog)")
        group.add_argument("--laser-tec-mode",          type=str,            help="laser TEC mode", choices=self.LASER_TEC_MODES)
        group.add_argument("--laser-warning-delay-sec", type=int,            help="set laser warning delay (sec)")

        group = parser.add_argument_group('Post-Processing')
        group.add_argument("--bin-2x2",                 action="store_true", help="apply 2x2 horizontal binning")

        group = parser.add_argument_group('Ramping')
        group.add_argument("--ramp-integ",              action="store_true", help="ramp integration time")
        group.add_argument("--ramp-gain",               action="store_true", help="ramp gain dB")
        group.add_argument("--ramp-avg",                action="store_true", help="ramp scan averaging")
        group.add_argument("--ramp-roi",                action="store_true", help="ramp vertical roi")
        group.add_argument("--ramp-repeats",            type=int,            help="spectra at each ramp step", default=5)

        group = parser.add_argument_group('Timing')
        group.add_argument("--power-watchdog-sec",      type=int,            help="set power watchdog (uint16 sec)")

        self.args = parser.parse_args()

    async def run(self):

        # note: will not connect to 'random' or first-found device, for laser safety reasons
        print(f"ble-util {self.VERSION}")
        if self.args.serial_number:
            print(f"Searching for {self.args.serial_number}...")
        elif self.args.first:
            print(f"Searching for first available WP-XS spectrometer...")
        else:
            print(f"No serial number specified, so will list search results and exit after {self.args.search_timeout_sec}sec.\n")

        # connect to device, read device information and characteristics
        await self.search_for_devices()
        if not self.client:
            return

        # always read EEPROM (needed to read spectra)
        await self.read_eeprom()
        if self.args.eeprom:
            self.display_eeprom()
            return

        # apply startup settings
        await self.apply_startup_settings()

        # timeouts
        if self.args.power_watchdog_sec is not None:
            await self.set_power_watchdog_sec(self.args.power_watchdog_sec)
        if self.args.laser_warning_delay_sec is not None:
            await self.set_laser_warning_delay_sec(self.args.laser_warning_delay_sec)

        # explicit laser control
        if self.args.laser_tec_mode is not None:
            await self.set_laser_tec_mode(self.args.laser_tec_mode)
        if self.args.laser_enable:
            await self.set_laser_enable(True)

        # apply acquisition parameters
        if self.args.integration_time_ms is not None and not self.args.ramp_integ:
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

    async def search_for_devices(self):
        self.start_time = datetime.now()

        # for some reason asyncio.timeout() isn't in my Python 3.10.15, so kludging
        async def cancel_task(sec):
            await asyncio.sleep(sec)
            self.stop_scanning()
        task = asyncio.create_task(cancel_task(self.args.search_timeout_sec))

        print(f"{datetime.now()} rssi local_name")
        async with BleakScanner(detection_callback=self.detection_callback, service_uuids=[self.WASATCH_SERVICE]) as scanner:
            await self.stop_event.wait()

        # scanner stops when block exits
        self.debug("scanner stopped")

        if self.client is None:
            if self.args.serial_number or self.args.first:
                print(f"spectrometer not found")
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
        if not self.keep_scanning:
            return

        if (datetime.now() - self.start_time).total_seconds() >= self.args.search_timeout_sec:
            self.debug("timeout expired")
            self.stop_scanning()
            return

        self.debug(f"discovered device {device}, advertisement_data {advertisement_data}")
        if not self.is_xs(device):
            return

        print(f"{datetime.now()} {advertisement_data.rssi:4d} {advertisement_data.local_name}")
        if self.args.serial_number is None and not self.args.first:
            return # we're just listing

        if not self.args.first and self.args.serial_number.lower() not in advertisement_data.local_name.lower():
            return # not the one

        self.debug("stopping scanner")
        self.stop_scanning()

        if self.args.debug:
            self.dump(device, advertisement_data)

        self.debug("instantiating BleakClient")
        self.client = BleakClient(address_or_ble_device=device, 
                                  disconnected_callback=self.disconnected_callback,
                                  timeout=self.args.search_timeout_sec)
        self.debug(f"BleakClient instantiated: {self.client}")

    def stop_scanning(self):
        self.keep_scanning = False
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

        print("Device Information:")
        for k, v in self.device_info.items():
            print(f"  {k:30s} {v}")

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
    
            if self.args.notifications:
                if "notify" in char.properties or "indicate" in char.properties:
                    if name == "BATTERY_STATUS":
                        self.debug(f"starting {name} notifications")
                        await self.client.start_notify(char.uuid, self.battery_notification)
                    elif name == "LASER_STATE":
                        self.debug(f"starting {name} notifications")
                        await self.client.start_notify(char.uuid, self.laser_state_notification)

    def battery_notification(self, sender, data):
        print(f"received BATTERY_STATUS notification: sender {sender}, data {data}")

    def laser_state_notification(self, sender, data):
        print(f"received LASER_STATE notification: sender {sender}, data {data}")

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
        name = name.upper()
        uuid = self.get_uuid_by_name(name)
        if uuid is None:
            raise RuntimeError(f"invalid characteristic {name}")

        if isinstance(data, list):
            data = bytearray(data)
        extra = self.expand_path(name, data) if name == "GENERIC" else ""

        if not quiet:
            code = self.code_by_name.get(name)
            self.debug(f">> write_char({name} 0x{code:02x}, {self.to_hex(data)}){extra}")
        await self.client.write_gatt_char(uuid, data, response=True) # ack all writes

    def expand_path(self, name, data):
        if name != "GENERIC":
            return [ f"0x{v:02x}" for v in data ]
        path = []
        header = True
        for i in range(len(data)):
            code = data[i]
            if header:
                name = self.generic_by_code[code]
                path.append(name)
                if code != 0xff:
                    header = False
            else:
                path.append(f"0x{code:02x}")
        return " [" + ", ".join(path) + "]"

    ############################################################################
    # Timeouts
    ############################################################################

    async def set_power_watchdog_sec(self, sec):
        tier = self.generics.get("NEXT_TIER")
        cmd = self.generics.get("SET_POWER_WATCHDOG_SEC")

        msb = (sec >> 8) & 0xff
        lsb = (sec     ) & 0xff

        await self.write_char("GENERIC", [tier, cmd, msb, lsb])

    async def set_laser_warning_delay_sec(self, sec):
        cmd = self.generics.get("SET_LASER_WARNING_DELAY_SEC")
        await self.write_char("GENERIC", [cmd, sec])

        self.laser_warning_delay_sec = sec
        # I don't _think_ I need to call sync_laser_state() here...

    ############################################################################
    # Laser Control
    ############################################################################

    async def set_laser_enable(self, flag):
        """
        @bug mode and type should be settable to 0xff (same with watchdog)
        """
        print(f"setting laser enable {flag}")
        self.laser_enable = flag
        await self.sync_laser_state()

    async def sync_laser_state(self):
        # kludge for BLE FW <4.8.9
        laser_warning_delay_ms = self.laser_warning_delay_sec * 1000

        data = [ 0x00,                   # mode
                 0x00,                   # type
                 0x01 if self.laser_enable else 0x00, 
                 0x00,                   # laser watchdog (DISABLE)
                 (laser_warning_delay_ms >> 8) & 0xff,
                 (laser_warning_delay_ms     ) & 0xff ]
               # 0xff                    # status mask
        await self.write_char("LASER_STATE", data)

    async def set_laser_tec_mode(self, mode: str):
        try:
            index = self.LASER_TEC_MODES.index(mode)
        except:
            print(f"ERROR: invalid laser TEC mode {mode}")
            return

        cmd = self.generics.get("SET_LASER_TEC_MODE")
        await self.write_char("GENERIC", [cmd, index])

    ############################################################################
    # Acquisition Parameters
    ############################################################################

    async def apply_startup_settings(self):
        # in case the last test left it with 5sec integration time or whatever
        if self.args.integration_time_ms is None:
            await self.set_integration_time_ms(self.eeprom["startup_integration_time_ms"])
        if self.args.gain_db is None:
            await self.set_gain_db(self.eeprom["gain"])
        # don't worry about startup_temp_degC (should be set by FW)

    async def set_integration_time_ms(self, ms):
        # using dedicated Characteristic, although 2nd-tier version now exists
        print(f"setting integration time to {ms}ms")
        data = [ 0x00,               # fixed
                 (ms >> 16) & 0xff,  # MSB
                 (ms >>  8) & 0xff,
                 (ms      ) & 0xff ] # LSB
        await self.write_char("INTEGRATION_TIME_MS", data)
        self.last_integration_time_ms = self.integration_time_ms
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

        msb = (n >> 8) & 0xff
        lsb = (n     ) & 0xff

        await self.write_char("GENERIC", [tier, cmd, msb, lsb])

    async def set_start_line(self, n):
        print(f"setting start line to {n}")
        tier = self.generics.get("NEXT_TIER")
        cmd = self.generics.get("SET_START_LINE")

        msb = (n >> 8) & 0xff
        lsb = (n     ) & 0xff

        await self.write_char("GENERIC", [tier, cmd, msb, lsb])

    async def set_stop_line(self, n):
        print(f"setting stop line to {n}")
        tier = self.generics.get("NEXT_TIER")
        cmd = self.generics.get("SET_STOP_LINE")

        msb = (n >> 8) & 0xff
        lsb = (n     ) & 0xff

        await self.write_char("GENERIC", [tier, cmd, msb, lsb])

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
        try:
            print("\nPress ctrl-C to exit...\n")
            while True:
                status = await self.get_status()
                print(f"{datetime.now()} {status}")
                sleep(1)
        except KeyboardInterrupt:
            print()

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
            hi = self.args.integration_time_ms if self.args.integration_time_ms else 2000
            step = hi // (n-1)
            self.ramping = True
            self.ramped_integ = [ max(10, i*step) for i in range(n) ]
            print(f"\nramping integration time: {self.ramped_integ}")

        if self.args.ramp_gain:
            hi = self.args.gain_db if self.args.gain_db else 30
            step = round(hi / (n-1), 1)
            self.ramping = True
            self.ramped_gain = [ round(i*step, 1) for i in range(n) ]
            print(f"\nramping gain dB: {self.ramped_gain}")

        if self.args.ramp_avg:
            self.ramping = True
            self.ramped_avg = [ 1, 5, 25, 125, 625 ]
            print(f"\nramping scan averaging: {self.ramped_avg}")

        if self.args.ramp_roi:
            self.ramping = True
            lo = self.args.start_line if self.args.start_line else 0
            hi = self.args.stop_line if self.args.stop_line else 1080
            rng = hi - lo
            step = rng // n
            self.ramped_roi = [ (lo + i*step, lo + (i+1)*step) for i in range(n) ]
            print(f"\nramping vertical ROI with step {step}: {self.ramped_roi}")

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

        try:
            # collect however many spectra were requested
            for step in range(self.args.spectra):
                await self.update_ramps(step)

                # if we're doing ramps, take a set of repeats at each step to capture any settling
                repeats = self.args.ramp_repeats if self.ramping else 1
                spectra = []
                for repeat in range(repeats):
                    spectrum = await self.get_spectrum()

                    # compute total start-to-start period
                    now = datetime.now()
                    start_time = self.last_spectrum_received if self.last_spectrum_received else self.start_time
                    elapsed_ms = int(round((now - start_time).total_seconds() * 1000, 0))
                    self.last_spectrum_received = now

                    hi = max(spectrum)
                    avg = sum(spectrum) / len(spectrum)
                    std = np.std(spectrum)
                    spectra.append(spectrum)

                    print(f"{now} received spectrum {step+1:3d}/{self.args.spectra} (elapsed {elapsed_ms:5d}ms, max {hi:8.2f}, avg {avg:8.2f}, std {std:8.2f}) {spectrum[:10]}")

                    if self.args.outfile:
                        with open(self.args.outfile, "a") as outfile:
                            outfile.write(f"{now}, " + ", ".join([str(v) for v in spectrum]) + "\n")
                            
                    if self.args.plot:
                        if not self.ramping and not self.args.overlay:
                            plt.clf()
                        plt.plot(xaxis, spectrum)
                        plt.draw()
                        plt.pause(0.01)

                if repeats > 1:
                    # if we're doing some kind of ramping, compute the average pixel stdev (pixel noise over time, not space)
                    stds = []
                    for px in range(len(spectra[0])):
                        px_std = np.std([ spectrum[px] for spectrum in spectra ])
                        stds.append(px_std)
                    avg_std = np.mean(stds)
                    print(f"average PIXEL stdev (over repeats) over the entire spectrum: {avg_std:.2f}\n")

        except KeyboardInterrupt:
            print()

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
        avg = self.args.scans_to_average if self.args.scans_to_average is not None else 1
        timeout_ms = 4 * max(self.last_integration_time_ms, self.integration_time_ms) * avg + 6000 # 4sec latency + 2sec buffer
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

            ####################################################################
            # validate response
            ####################################################################

            ok = True
            response_len = len(response)
            if (response_len < header_len):
                print(f"ERROR: received invalid READ_SPECTRUM response of {response_len} bytes (missing header): {response}")
                ok = False
            else:
                # check for official NAK
                first_pixel = int((response[0] << 8) | response[1]) # big-endian int16
                if first_pixel == 0xffff:
                    # this is a NAK, check for detail
                    ok = False
                    if len(response) > 2:
                        error_code = response[2]
                        if error_code < len(self.ACQUIRE_ERRORS):
                            error_str = self.ACQUIRE_ERRORS[error_code]
                            if error_str != "NONE":
                                print(f"ERROR: READ_SPECTRUM returned {error_str}")
                        else:
                            print(f"ERROR: unknown READ_SPECTRUM error_code {error_code}")
                    if len(response) > 3:
                        print("ERROR: trailing data after NAK error code: {self.to_hex(response)}")
                elif first_pixel != pixels_read:
                    self.debug(f"WARNING: received unexpected first pixel {first_pixel} (pixels_read {pixels_read})")
                    ok = False
                elif (response_len < header_len or response_len % 2 != 0):
                    print(f"ERROR: received invalid READ_SPECTRUM response of {response_len} bytes (odd length): {response}")
                    ok = False

            if not ok:
                sleep(0.2)
                continue
            
            ####################################################################
            # apparently it was a valid response
            ####################################################################

            pixels_in_packet = int((response_len - header_len) / 2)
            for i in range(pixels_in_packet):
                # pixel intensities are little-endian uint16
                offset = header_len + i * 2
                intensity = int((response[offset+1] << 8) | response[offset])

                spectrum[pixels_read] = intensity
                pixels_read += 1

                if pixels_read == self.pixels:
                    # self.debug("read complete spectrum")
                    if (i + 1 != pixels_in_packet):
                        print(f"ERROR: ignoring {pixels_in_packet - (i + 1)} trailing pixels")

        if self.args.bin_2x2:
            # note, this needs updated for 633XS
            self.debug("applying 2x2 binning")
            binned = []
            for i in range(len(spectrum)-1):
                binned.append((spectrum[i] + spectrum[i+1]) / 2.0)
            binned.append(spectrum[-1])
            spectrum = binned
            
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
        print(msg)

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

    def to_hex(self, a):
        return "[ " + ", ".join([f"0x{v:02x}" for v in a]) + " ]"

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
