import platform
import matplotlib.pyplot as plt
import numpy as np
import argparse
import asyncio
import struct
import re

from time import sleep
from bleak import BleakScanner, BleakClient
from datetime import datetime
from functools import partial

import EEPROMFields

debugging = False
def debug(msg):
    if debugging:
        print(f"{datetime.now()} DEBUG: {msg}")

def to_hex(a):
    if a is None:
        return "[ ]"
    return "[ " + ", ".join([f"0x{v:02x}" for v in a]) + " ]"

class Fixture:
    """
    Note this script is currently coded to ENG-0120 BLE API rev 7.

    @todo It appears notifications don't work on Windows?!?
    """
    VERSION = "1.0.5"

    WASATCH_SERVICE   = "D1A7FF00-AF78-4449-A34F-4DA1AFAF51BC"
    DISCOVERY_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"

    LASER_TEC_MODES = ['OFF', 'ON', 'AUTO', 'AUTO_ON']

    ACQUIRE_STATUS_CODES = {
         0: ("NAK",                         "No error, the spectrum just isn't ready yet"),
         1: ("ERR_BATT_SOC_INFO_NOT_RCVD",  "Can't read battery, and therefore can't take Auto-Dark or Auto-Raman spectra"),
         2: ("ERR_BATT_SOC_TOO_LOW",        "Battery is too low to take Auto-Dark or Auto-Raman spectra"),
         3: ("ERR_LASER_DIS_FLR",           "Failure disabling the laser"),
         4: ("ERR_LASER_ENA_FLR",           "Failure enabling the laser"),
         5: ("ERR_IMG_SNSR_IN_BAD_STATE",   "The sensor is not able to take spectra"),
         6: ("ERR_IMG_SNSR_STATE_TRANS_FLR","The sensor failed to apply acquisition parameters"),
         7: ("ERR_SPEC_ACQ_SIG_WAIT_TMO",   "The sensor failed to take a spectrum (timeout exceeded)"),
        32: ("AUTO_OPT_TARGET_RATIO",       "Auto-Raman is in the process of optimizing acquisition parameters"),
        33: ("TAKING_DARK",                 "taking spectra (no laser)"),
        34: ("LASER_WARNING_DELAY",         "paused during laser warning delay period"),
        35: ("LASER_WARMUP",                "paused during laser warmup period"),
        36: ("TAKING_RAMAN",                "taking spectra (laser enabled)"),
    }

    ############################################################################
    # Lifecycle
    ############################################################################

    def __init__(self):

        # scanning
        self.client = None                                  # instantiated BleakClient
        self.keep_scanning = True
        self.stop_scanning_event = asyncio.Event()

        # EEPROM
        self.eeprom = None
        self.eeprom_field_loc = EEPROMFields.get_eeprom_fields()

        # Device Settings
        self.integration_time_ms = 0 # read from EEPROM startup field
        self.last_integration_time_ms = 2000
        self.scans_to_average = 1
        self.last_spectrum_received = None
        self.laser_enable = False
        self.laser_warning_delay_sec = 3

        self.notifications = set()                          # all Characteristics to which we're subscribed for notifications

        # Characteristics
        self.code_by_name = { "LASER_STATE":             0xff03,
                              "ACQUIRE":                 0xff04,
                              "BATTERY_STATE":           0xff09,
                              "GENERIC":                 0xff0a }
        self.name_by_uuid = { self.wrap_uuid(code): name for name, code in self.code_by_name.items() }

        #                  Name                        Lvl  Set   Get Size
        self.generics = Generics()
        self.generics.add("LASER_TEC_MODE",             0, 0x84, 0x85, 1)
        self.generics.add("GAIN_DB",                    0, 0xb7, 0xc5, 2, epsilon=0.01)
        self.generics.add("INTEGRATION_TIME_MS",        0, 0xb2, 0xbf, 3)
        self.generics.add("LASER_WARNING_DELAY_SEC",    0, 0x8a, 0x8b, 1)
        self.generics.add("EEPROM_DATA",                1, None, 0x01, 1)
        self.generics.add("START_LINE",                 1, 0x21, 0x22, 2)
        self.generics.add("STOP_LINE",                  1, 0x23, 0x24, 2)
        self.generics.add("AMBIENT_TEMPERATURE_DEG_C",  1, None, 0x2a, 1)
        self.generics.add("POWER_WATCHDOG_SEC",         1, 0x30, 0x31, 2)
        self.generics.add("SCANS_TO_AVERAGE",           1, 0x62, 0x63, 2)

        self.parse_args()

    def parse_args(self):
        global debugging

        parser = argparse.ArgumentParser(
            description="Command-line utility for testing and characterizing BLE spectrometers",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",                  action="store_true", help="debug output")

        group = parser.add_argument_group('Discovery')
        group.add_argument("--serial-number",           type=str,            help="auto-connect on discovery")
        group.add_argument("--first",                   action="store_true", help="connect to first-discovered 'WP-XS' device (required for Windows?)")
        group.add_argument("--eeprom",                  action="store_true", help="display EEPROM and exit")
        group.add_argument("--monitor",                 action="store_true", help="monitor battery, laser state etc")
        group.add_argument("--search-timeout-sec",      type=int,            help="how long to search for spectrometers", default=30)

        group = parser.add_argument_group('Spectra')
        group.add_argument("--spectra",                 type=int,            help="number of spectra to acquire", default=5)
        group.add_argument("--auto-dark",               action="store_true", help="take Auto-Dark measurements")
        group.add_argument("--auto-raman",              action="store_true", help="take Auto-Raman measurements")
        group.add_argument("--outfile",                 type=str,            help="save spectra to CSV file")
        group.add_argument("--plot",                    action="store_true", help="graph spectra")
        group.add_argument("--overlay",                 action="store_true", help="overlay spectra on graph")
        group.add_argument("--delay-ms",                type=int,            help="intra-spectra delay", default=0)
        group.add_argument("--keep-waiting",            action="store_true", help="don't timeout")
                                                         
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

        group = parser.add_argument_group('Misc')
        group.add_argument("--power-watchdog-sec",      type=int,            help="set power watchdog (uint16 sec)")
        group.add_argument("--accessors",               action="store_true", help="exercise getter/setters")
        group.add_argument("--setter-delay-ms",         type=int,            help="minimum delay / settle time after writing generic setter", default=1000)

        self.args = parser.parse_args()

        if self.args.debug:
            debugging = True

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

        # exercise accessors
        if self.args.accessors:
            await self.exercise_accessors()

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

        # shutdown
        if self.args.laser_enable:
            await self.set_laser_enable(False)
        await self.stop_notifications()

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
            await self.stop_scanning_event.wait()

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
        print(f"initial connection took {elapsed_sec:.2f} sec")

    def detection_callback(self, device, advertisement_data):
        """
        discovered device 13874014-5EDA-5E6B-220E-605D00FE86DF: WP-SiG:WP-01791, 
        advertisement_data AdvertisementData(local_name='WP-SiG:WP-01791', 
                                             service_uuids=['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc'], 
                                             tx_power=0, rssi=-67)

        @param device is a bleak.backends.device.BLEDevice
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

        self.dump(device, advertisement_data)

        self.debug("instantiating BleakClient")
        self.client = BleakClient(address_or_ble_device=device, 
                                  disconnected_callback=self.disconnected_callback,
                                  timeout=self.args.search_timeout_sec)
        self.debug(f"BleakClient instantiated: {self.client}")

    def stop_scanning(self):
        self.keep_scanning = False
        self.stop_scanning_event.set()

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
        primary_service = None
        for service in self.client.services:
            if service.uuid.lower() == self.WASATCH_SERVICE.lower():
                primary_service = service
                
        if primary_service is None:
            return

        # iterate over standard Characteristics
        # @see https://bleak.readthedocs.io/en/latest/api/client.html#gatt-characteristics
        self.char_by_name = {}
        for char in primary_service.characteristics:
            name = self.get_name_by_uuid(char.uuid)
            self.char_by_name[name] = char

        sys = platform.system()
        self.debug("Characteristics:")
        for name in ['GENERIC', 'LASER_STATE', 'ACQUIRE', 'BATTERY_STATE']:
            char = self.char_by_name[name]
            extra = ""

            if "write-without-response" in char.properties:
                extra += f", Max write w/o rsp size: {char.max_write_without_response_size}"

            props = ",".join(char.properties)
            self.debug(f"  {name:30s} {char.uuid} ({props}){extra}")
    
            if "notify" in char.properties or "indicate" in char.properties:
                if name == "BATTERY_STATE":
                    self.debug(f"starting {name} notifications")
                    await self.client.start_notify(char.uuid, self.battery_notification)
                    self.notifications.add(char.uuid)
                elif name == "LASER_STATE":
                    self.debug(f"starting {name} notifications")
                    await self.client.start_notify(char.uuid, self.laser_state_notification)
                    self.debug(f"back from start_notify")
                    self.notifications.add(char.uuid)
                elif name == "GENERIC":
                    self.debug(f"starting {name} notifications")
                    await self.client.start_notify(char.uuid, self.generics.notification_callback)
                    self.notifications.add(char.uuid)
                elif name == "ACQUIRE":
                    self.debug(f"starting {name} notifications")
                    await self.client.start_notify(char.uuid, self.acquire_notification)
                    self.notifications.add(char.uuid)

    async def stop_notifications(self):
        for uuid in self.notifications:
            await self.client.stop_notify(uuid)

    def battery_notification(self, sender, data):
        charging = data[0] != 0
        perc = int(data[1])
        print(f"{datetime.now()} received BATTERY_STATE notification: level {perc}%, charging {charging} (data {data})")

    def laser_state_notification(self, sender, data):
        status = self.parse_laser_state(data)
        print(f"{datetime.now()} received LASER_STATE notification: sender {sender}, data {data}: {status}")

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
            raise RuntimeError(f"characteristic {name} returned insufficient data ({len(response)} < {min_len})")

        buf = bytearray()
        for byte in response:
            buf.append(byte)
        return buf

    async def write_char(self, name, data, quiet=False, callback=None, ack_name=None):
        name = name.upper()
        uuid = self.get_uuid_by_name(name)
        if uuid is None:
            raise RuntimeError(f"invalid characteristic {name}")
        extra = []

        if name == "GENERIC":
            # STEP FIVE: allocate a new sequence number, and associate it with the passed callback
            if callback is None and ack_name is not None:
                # we weren't given an explicit callback, but this GENERIC opcode 
                # generates an acknowledgement, so setup a lambda to catch it (so
                # we can block on it before returning)
                callback = partial(self.generics.process_acknowledgement, name=ack_name)
            seq = self.generics.next_seq(callback)
            prefixed = [ seq ]
            for v in data:
                prefixed.append(v)
            data = prefixed
            extra.append(self.expand_path(name, data))

        if not quiet:
            code = self.code_by_name.get(name)
            self.debug(f">> write_char({name} 0x{code:02x}, {to_hex(data)}){', '.join(extra)}")

        if isinstance(data, list):
            data = bytearray(data)

        # MZ: I'm not sure why all writes require a response, but empirical 
        # testing indicates we reliably get randomly scrambled EEPROM contents 
        # without this.

        # STEP SEVEN: actually write the cmd (or for Generic reads, "read request") to the Peripheral
        await self.client.write_gatt_char(uuid, data, response=True)

        if ack_name is not None:
            # block on the acknowledgement we created above
            self.debug(f"write_char: waiting for {ack_name} ack")
            await self.generics.wait(ack_name)

    def expand_path(self, name, data):
        if name != "GENERIC":
            return [ f"0x{v:02x}" for v in data ]
        path = [ f"SEQ 0x{data[0]:02x}" ]
        header = True
        for i in range(1, len(data)):
            if header:
                code = data[i]
                name = self.generics.get_name(code)
                path.append(name)
                if code != 0xff:
                    header = False
            else:
                path.append(f"0x{data[i]:02x}")
        return "[" + ", ".join(path) + "]"

    ############################################################################
    # Timeouts
    ############################################################################

    async def set_power_watchdog_sec(self, sec):
        await self.write_char("GENERIC", self.generics.generate_write_request("POWER_WATCHDOG_SEC", sec))

    async def set_laser_warning_delay_sec(self, sec):
        await self.write_char("GENERIC", self.generics.generate_write_request("LASER_WARNING_DELAY_SEC", sec))

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

    def parse_laser_state(self, data):
        result = { 'laser_enable': False, 'laser_watchdog_sec': 0, 'status_mask': 0, 'laser_firing': False, 'interlock_closed': False }
        size = len(data)
        #if size > 0: result['mode']              = data[0]
        #if size > 1: result['type']              = data[1]
        if size > 2: result['laser_enable']       = data[2] != 0
        if size > 3: result['laser_watchdog_sec'] = data[3]
        # ignore bytes 4-5 (reserved)
        if size > 6: 
            result['status_mask']                 = data[6]
            result['interlock_closed']            = data[6] & 0x01 != 0
            result['laser_firing']                = data[6] & 0x02 != 0
        return result

    async def set_laser_tec_mode(self, mode: str):
        index = self.LASER_TEC_MODES.index(mode)
        await self.write_char("GENERIC", self.generics.generate_write_request("LASER_TEC_MODE", index))

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
        name = "INTEGRATION_TIME_MS"
        print(f"setting {name} to {ms}ms")
        await self.write_char("GENERIC", self.generics.generate_write_request(name, ms), ack_name=name)

        self.last_integration_time_ms = self.integration_time_ms
        self.integration_time_ms = ms

    async def set_gain_db(self, db):
        name = "GAIN_DB"
        print(f"setting {name} to {db}dB")
        await self.write_char("GENERIC", self.generics.generate_write_request(name, db), ack_name=name)

    async def set_scans_to_average(self, n):
        name = "SCANS_TO_AVERAGE"
        print(f"setting {name} to {n}")
        await self.write_char("GENERIC", self.generics.generate_write_request(name, n), ack_name=name)
        self.scans_to_average = n

    async def set_start_line(self, n):
        print(f"setting start line to {n}")
        await self.write_char("GENERIC", self.generics.generate_write_request("START_LINE", n))

    async def set_stop_line(self, n):
        print(f"setting stop line to {n}")
        await self.write_char("GENERIC", self.generics.generate_write_request("STOP_LINE", n))

    async def set_vertical_roi(self, pair):
        await self.set_start_line(pair[0])
        await self.set_stop_line (pair[1])

    ############################################################################
    # Monitor
    ############################################################################

    async def get_battery_state(self):
        """
        These will be pushed automatically 1/min from Central, if-and-only-if
        no acquisition is occuring at the time of the scheduled event. However,
        at least some(?) clients (Bleak on MacOS) don't seem to receive the
        notifications until the next explicit read/write of a Characteristic 
        (any Chararacteristic? seemingly observed with ACQUIRE_CMD).
        """
        buf = await self.read_char("BATTERY_STATE", 2)
        self.debug(f"battery response: {buf}")
        return { 'charging': buf[0] != 0,
                 'perc': int(buf[1]) }

    async def get_laser_state(self):
        retval = {}
        for k in [ 'mode', 'type', 'enable', 'watchdog_sec', 'mask', 'interlock_closed', 'laser_firing' ]:
            retval[k] = 'UNKNOWN'
            
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
        battery_state = await self.get_battery_state()
        battery_perc = f"{battery_state['perc']:3d}%"
        battery_charging = 'charging' if battery_state['charging'] else 'discharging'

        laser_state = await self.get_laser_state()
        laser_firing = laser_state['laser_firing']
        interlock_closed = 'closed (armed)' if laser_state['interlock_closed'] else 'open (safe)'

        amb_temp = await self.get_generic_value("AMBIENT_TEMPERATURE_DEG_C")

        return f"Battery {battery_perc} ({battery_charging}), Laser {laser_firing}, Interlock {interlock_closed}, Amb {amb_temp}°C"

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
    # Generics
    ############################################################################

    # these methods belong in the Fixture, rather than Generics, because they
    # use self.debug, .write_char etc
    
    async def get_generic_value(self, name):
        # STEP ONE: generate the payload for writing the "read request" for this particular attribute to the Generic characteristic
        request = self.generics.generate_read_request(name)
        self.debug(f"get_generic: querying {name} ({to_hex(request)})")

        # STEP FOUR: write the "read request" to the attribute. Store a callback
        # which should be triggered when the response notification (carrying the
        # same sequence number) is returned.
        await self.write_char("GENERIC", request, callback=lambda data: self.generics.process_response(name, data))

        # STEP EIGHTEEN: this blocking wait will be satisfied after steps 4-17 are complete
        self.debug(f"get_generic: waiting on {name}")
        await self.generics.wait(name)

        # STEP NINETEEN: read the deserialized response value we stored in the notification callback
        self.debug(f"get_generic: taking response from {name}")
        value = self.generics.get_value(name)
        self.debug(f"get_generic: done (value {value})")

        # STEP TWENTY: return the value to whoever called this function.
        return value

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
            collection = []
            for step in range(self.args.spectra):
                await self.update_ramps(step)

                # if we're doing ramps, take a set of repeats at each step to capture any settling
                repeats = self.args.ramp_repeats if self.ramping else 1
                spectra = []
                for repeat in range(repeats):
                    start_time = datetime.now()
                    spectrum = await self.get_spectrum()

                    # compute total start-to-start period
                    now = datetime.now()
                    # start_time = self.last_spectrum_received if self.last_spectrum_received else self.start_time
                    elapsed_ms = int(round((now - start_time).total_seconds() * 1000, 0))
                    self.last_spectrum_received = now

                    hi = max(spectrum)
                    avg = sum(spectrum) / len(spectrum)
                    std = np.std(spectrum)
                    spectra.append(spectrum)
                    collection.append(spectrum)

                    print(f"{now} received spectrum {step+1:3d}/{self.args.spectra} (elapsed {elapsed_ms:5d}ms, max {hi:8.2f}, avg {avg:8.2f}, std {std:8.2f}) {spectrum[:10]}")

                    if self.args.outfile:
                        with open(self.args.outfile, "a") as outfile:
                            outfile.write(f"{now}, " + ", ".join([str(v) for v in spectrum]) + "\n")
                            
                    if self.args.plot:
                        if not self.ramping and not self.args.overlay:
                            plt.clf()
                        debug(f"graphing x {xaxis[:5]}, y {spectrum[:5]}")
                        plt.plot(xaxis, spectrum)
                        plt.draw()
                        plt.pause(0.01)

                    await asyncio.sleep(self.args.delay_ms / 1000.0)

                if repeats > 1:
                    # if we're doing some kind of ramping, compute the average pixel stdev (pixel noise over time, not space)
                    stds = []
                    for px in range(len(spectra[0])):
                        px_std = np.std([ spectrum[px] for spectrum in spectra ])
                        stds.append(px_std)
                    avg_std = np.mean(stds)
                    print(f"average PIXEL stdev (over repeats) over the entire spectrum: {avg_std:.2f}\n")

            if repeats > 1:
                # if we're doing some kind of ramping, compute the average pixel stdev (pixel noise over time, not space)
                stds = []
                for px in range(len(collection[0])):
                    px_std = np.std([ spectrum[px] for spectrum in collection ])
                    stds.append(px_std)
                avg_std = np.mean(stds)
                print(f"average PIXEL stdev (over collection) over the entire spectrum: {avg_std:.2f}\n")

        except KeyboardInterrupt:
            print()

    def parse_acquire_status(self, status, payload):
        if status not in self.ACQUIRE_STATUS_CODES:
            raise RuntimeError("ACQUIRE notification included unsupported status code 0x{status:02x}, payload {payload}")

        short, long = self.ACQUIRE_STATUS_CODES[status]
        msg = f"{short}: {long}"

        # special handling for status codes including payload
        if status == 32: 
            targetRatio = int(payload[0])
            msg += f" (target ratio {targetRatio}%)"
        elif status in [33, 34, 35, 36]:
            currentStep = int(payload[0] << 8 | payload[1])
            totalSteps  = int(payload[2] << 8 | payload[3])
            if totalSteps > 1:
                msg += f" (step {currentStep+1}/{totalSteps})" 

        return msg
    
    def acquire_notification(self, sender, data):
        ok = True
        if (len(data) < 3):
            raise RuntimeError(f"received invalid ACQUIRE notification of {len(data)} bytes: {data}")

        # first two bytes declare whether it's a status message or spectral data
        first_pixel = int((data[0] << 8) | data[1]) # big-endian int16

        if first_pixel == 0xffff:
            status = data[2]
            payload = data[3:]
            msg = self.parse_acquire_status(status, payload)
            self.debug(f"acquire_notification: {msg}")
            return

        ########################################################################
        # apparently it's spectral data
        ########################################################################

        # validate first_pixel
        if first_pixel != self.pixels_read:
            raise RuntimeError(f"received first_pixel {first_pixel} when pixels_read {self.pixels_read}")

        spectral_data = data[2:]
        pixels_in_packet = int(len(spectral_data) / 2)

        for i in range(pixels_in_packet):
            # pixel intensities are little-endian uint16
            offset = i * 2
            intensity = int((spectral_data[offset+1] << 8) | spectral_data[offset])

            self.spectrum[self.pixels_read] = intensity
            self.pixels_read += 1

            if self.pixels_read == self.pixels:
                # self.debug("read complete spectrum")
                if (i + 1 != pixels_in_packet):
                    raise RuntimeError(f"trailing pixels in packet")

    async def get_spectrum(self):
        self.pixels_read = 0
        self.spectrum = [0] * self.pixels

        # determine which type of measurement
        if self.args.auto_raman: 
            arg = 2
        elif self.args.auto_dark: 
            arg = 1
        else: 
            arg = 0

        # send the ACQUIRE
        await self.write_char("ACQUIRE", [arg]) # , quiet=True)

        # compute timeout
        timeout_ms = 4 * max(self.last_integration_time_ms, self.integration_time_ms) * self.scans_to_average + 6000 # 4sec latency + 2sec buffer

        # wait for spectral data to arrive
        start_time = datetime.now()
        while self.pixels_read < self.pixels:
            if not self.args.keep_waiting and (datetime.now() - start_time).total_seconds() * 1000 > timeout_ms:
                raise RuntimeError(f"failed to read spectrum within timeout {timeout_ms}ms")

            # self.debug(f"still waiting for spectra ({self.pixels_read}/{self.pixels} read)")
            await asyncio.sleep(0.2)

        ########################################################################
        # post-processing
        ########################################################################

        if self.args.bin_2x2:
            # note, this needs updated for 633XS
            self.debug("applying 2x2 binning")
            binned = []
            for i in range(len(spectrum)-1):
                binned.append((spectrum[i] + spectrum[i+1]) / 2.0)
            binned.append(spectrum[-1])
            spectrum = binned
            
        return self.spectrum

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
            msg += f" ({self.wavenumbers[0]:.2f}, {self.wavenumbers[-1]:.2f} 1/cm)"
        try:
            print(msg)
        except:
            msg = msg.encode('ascii', errors='ignore')
            print(f"simplified: {msg}")

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

        self.excitation = self.eeprom["excitation_nm_float"] # @todo update for MultiWavelengthCalibration
        self.wavenumbers = None
        if self.excitation:
            self.wavenumbers = [ (1e7/self.excitation - 1e7/nm) for nm in self.wavelengths ]

    async def read_eeprom_pages(self):
        """ tweaked version of get_generic_value """
        start_time = datetime.now()

        self.eeprom = {}
        self.pages = []

        name = "EEPROM_DATA"
        for page in range(8):
            buf = bytearray()
            for subpage in range(4):
                
                request = self.generics.generate_read_request(name)
                request.append(0) # page is big-endian uint16
                request.append(page)
                request.append(subpage)

                self.debug(f"read_eeprom_pages: querying {name} ({to_hex(request)})")
                await self.write_char("GENERIC", request, callback=lambda data: self.generics.process_response(name, data))

                self.debug(f"read_eeprom_pages: waiting on {name}")
                await self.generics.wait(name)

                data = self.generics.get_value(name)
                self.debug(f"read_eeprom_pages: received page {page}, subpage {subpage}: {data}")

                for byte in data:
                    buf.append(byte)
            self.pages.append(buf)

        elapsed_sec = (datetime.now() - start_time).total_seconds()
        print(f"reading eeprom took {elapsed_sec:.2f} sec")

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
    # Accessors
    ############################################################################

    async def exercise_accessors(self):
        # integration time
        # gain
        # laser state (enable, watchdog, ...)

        await self.exercise_generic_accessors()

        # reset this to avoid crazy timeout
        await self.set_scans_to_average(1)

    async def exercise_generic_accessors(self):
        print("Exercising Generic Accessors")
        for name, values in [ [ 'LASER_TEC_MODE',          [ 0, 1, 2, 3                 ] ],
                              [ 'INTEGRATION_TIME_MS',     [ 1, 10, 100, 1000, 2000     ] ],
                              [ 'LASER_WARNING_DELAY_SEC', [ 0, 5, 10                   ] ],
                              [ 'GAIN_DB',                 [ 0, 0.1, 0.9, 8, 16, 24, 30 ] ],
                              [ 'START_LINE',              [ 0, 400, 800                ] ],
                              [ 'STOP_LINE',               [ 1, 400, 1080               ] ],
                              [ 'POWER_WATCHDOG_SEC',      [ 0, 30, 120                 ] ],
                              [ 'SCANS_TO_AVERAGE',        [ 1, 5, 25, 125, 625         ] ] ]:

            print(f"  {name}")
            for value in values:
                # write value
                self.debug(f"setting GENERIC {name} to value {value}")
                await self.write_char("GENERIC", self.generics.generate_write_request(name, value))

                self.debug(f"waiting {self.args.setter_delay_ms}ms for setter to 'take'")
                await asyncio.sleep(self.args.setter_delay_ms / 1000)

                # read-back value from device
                received_value = await self.get_generic_value(name)

                # validate response
                if self.generics.equals(name, value):
                    print(f"    SUCCESS: {name} --> {value}")
                    self.debug("")
                else:
                    raise RuntimeError(f"sent {name} value {value}, but read {received_value}")

    ############################################################################
    # Utility
    ############################################################################

    def debug(self, msg):
        debug(msg)

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

class Generic:
    """ encapsulates paired setter and getter accessors for a single attribute """
    def __init__(self, name, tier, setter, getter, size, epsilon):
        self.name    = name
        self.tier    = tier # 0, 1 or 2
        self.setter  = setter
        self.getter  = getter
        self.size    = size
        self.epsilon = epsilon

        self.value = None
        self.event = asyncio.Event()
    
    def serialize(self, value):
        data = []
        if self.name == "GAIN_DB":
            data.append(int(value) & 0xff)
            data.append(int((value - int(value)) * 256) & 0xff)
        else: 
            # assume big-endian uint[size]            
            for i in range(self.size):
                data.append((value >> (8 * (self.size - (i+1)))) & 0xff)
        return data

    def deserialize(self, data):
        # STEP SIXTEEN: deserialize the returned Generic response payload according to the attribute type
        if self.name == "GAIN_DB":
            return data[0] + data[1] / 256.0
        elif self.name == "EEPROM_DATA":
            return data
        else:
            # by default, treat as big-endian uint
            value = 0
            for byte in data:
                value <<= 8
                value |= byte
            return value

    def generate_write_request(self, value):
        if self.setter is None:
            raise RuntimeError(f"Generic {self.name} is read-only")
        request = [ 0xff for _ in range(self.tier) ]
        request.append(self.setter)
        request.extend(self.serialize(value))
        return request

    def generate_read_request(self):
        # STEP THREE: generate the "read request" payload for this attribute
        if self.getter is None:
            raise RuntimeError(f"Generic {self.name} is write-only")
        request = [ 0xff for _ in range(self.tier) ]
        request.append(self.getter)
        return request

class Generics:
    """ Facade to access all Generic attributes in the BLE interface """

    RESPONSE_ERRORS = [ 'OK', 'NO_RESPONSE_FROM_HOST', 'FPGA_READ_FAILURE', 'INVALID_ATTRIBUTE', 'UNSUPPORTED_COMMAND' ]

    def __init__(self):
        self.seq = 0
        self.generics = {}
        self.callbacks = {}

    def next_seq(self, callback=None):
        self.seq = (self.seq + 1) % 256
        if self.seq in self.callbacks:
            raise RuntimeError("seq {self.seq} has unprocessed callback {self.callbacks[self.seq]}")
        elif callback:
            # STEP SIX: store the callback function in a table, keyed on the new sequence number
            self.callbacks[self.seq] = callback
        return self.seq

    def get_callback(self, seq):
        # STEP ELEVEN: remove the stored callback from the table, so it won't accidentally be re-used
        if seq in self.callbacks:
            return self.callbacks.pop(seq)

        # probably an uncaught acknowledgement from a generic setter like SET_INTEGRATION_TIME_MS
        debug(f"get_callback: seq {seq} not found in callbacks")

    def add(self, name, tier, setter, getter, size, epsilon=0):
        self.generics[name] = Generic(name, tier, setter, getter, size, epsilon)

    def generate_write_request(self, name, value):
        return self.generics[name].generate_write_request(value)

    def generate_read_request(self, name):
        # STEP TWO: generate the "read request" payload for the named attribute
        return self.generics[name].generate_read_request()

    def get_value(self, name):
        return self.generics[name].value

    async def wait(self, name):
        await self.generics[name].event.wait()
        self.generics[name].event.clear()

    async def process_acknowledgement(self, data, name):
        debug(f"received acknowledgement for {name}")
        generic = self.generics[name]
        generic.event.set()

    async def process_response(self, name, data):
        # STEP THIRTEEN: this is the standard callback triggered after receiving
        # a notification from the Generic Characteristic

        # STEP FOURTEEN: lookup the specific Generic attribute (AMBIENT_TEMPERATURE_DEG_C, etc) associated with this transaction
        generic = self.generics[name]

        # STEP FIFTEEN: parse the response payload according to the attribute
        generic.value = generic.deserialize(data)

        # STEP SEVENTEEN: raise the asynchronous "event" flag to tell the 
        # await'ing requester that the response value is now available and stored
        # in the Generic object
        generic.event.set()

    async def notification_callback(self, sender, data):
        # STEP EIGHT: we have received a response notification from the Generic Characteristic

        debug(f"received GENERIC notification from sender {sender}, data {to_hex(data)}")

        # STEP NINE: extract the sequence number from the notification response
        result = None
        if len(data) < 3:
            seq, err = data[0], data[1]
        else:
            seq, err, result = data[0], data[1], data[2:]

        if err < len(self.RESPONSE_ERRORS):
            response_error = self.RESPONSE_ERRORS[err]
        else:
            response_error = f"UNSUPPORTED RESPONSE_ERROR: 0x{err}"

        if response_error != "OK":
            raise RuntimeError(f"GENERIC notification included error code {err} ({response_error}); data {to_hex(data)}")

        # STEP TEN: lookup the stored callback for this sequence number
        #
        # pass the response data, minus the sequence and error-code header, to 
        # the registered callback function for that sequence ID
        callback = self.get_callback(seq)

        # STEP TWELVE: actually call the callback
        if callback:
            await callback(result)
        
    def get_name(self, code):
        if code == 0xff:
            return "NEXT_TIER"

        for name, generic in self.generics.items():
            if code == generic.setter:
                return f"SET_{name}"
            elif code == generic.getter:
                return f"GET_{name}"
        return "UNKNOWN"

    def equals(self, name, expected):
        actual  = self.generics[name].value
        epsilon = self.generics[name].epsilon
        delta   = abs(actual - expected)
        return delta <= epsilon

if __name__ == "__main__":
    fixture = Fixture()
    asyncio.run(fixture.run())

#    loop = asyncio.get_event_loop()
#    asyncio.ensure_future(fixture.run())
#    loop.run_forever()
#    loop.close()
