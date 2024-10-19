import argparse
import asyncio

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

        self.char_code_by_name = { "INTEGRATION_TIME_MS":   0xff01, 
                                   "GAIN_DB":               0xff02,
                                   "LASER_STATE":           0xff03,
                                   "ACQUIRE_SPECTRUM":      0xff04,
                                   "SPECTRUM_CMD":          0xff05,
                                   "READ_SPECTRUM":         0xff06,
                                   "EEPROM_CMD":            0xff07,
                                   "EEPROM_DATA":           0xff08,
                                   "BATTERY_STATUS":        0xff09,
                                   "GENERIC_MESSAGE":       0xff0a }

        self.generics = { "SET_GAIN_DB":                    0xb7,
                          "GET_GAIN_DB":                    0xc5,
                          "SET_INTEGRATION_TIME_MS":        0xb2,
                          "GET_INTEGRATION_TIME_MS":        0xbf,
                          "GET_LASER_WARNING_DELAY_SEC":    0x8b,
                          "SET_LASER_WARNING_DELAY_SEC":    0x8a,
                          "SECOND_TIER":                    0xff,
                                                            
                          "SET_START_LINE":                 0x21,
                          "SET_STOP_LINE":                  0x23,
                          "GET_AMBIENT_TEMPERATURE":        0x2a,
                          "GET_POWER_WATCHDOG_SEC":         0x31,
                          "SET_POWER_WATCHDOG_SEC":         0x30,
                          "SET_SCANS_TO_AVERAGE":           0x62,
                          "GET_SCANS_TO_AVERAGE":           0x63,
                          "THIRD_TIER":                     0xff }

        self.char_name_by_uuid = {}
        for name, code in self.char_code_by_name.items():
            self.char_name_by_uuid[self.wrap_uuid(code)] = name

        self.parse_args()

    def parse_args(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--timeout-sec",         type=int,            help="how long to search for spectrometers", default=30)
        parser.add_argument("--serial-number",       type=str,            help="delay n ms between spectra")

        # not yet implemented
        parser.add_argument("--eeprom",              action="store_true", help="load and parse the EEPROM")
        parser.add_argument("--monitor",             action="store_true", help="monitor battery, laser state etc")

        parser.add_argument("--integration-time-ms", type=int,            help="set integration time")
        parser.add_argument("--gain-db",             type=float,          help="set gain (dB)")
        parser.add_argument("--scans-to-average",    type=int,            help="set scan averaging")
        parser.add_argument("--laser-enable",        action="store_true", help="fire the laser")

        parser.add_argument("--spectra",             type=int,            help="spectra to acquire", default=5)
        parser.add_argument("--outfile",             type=str,            help="save spectra to CSV file")
        parser.add_argument("--auto-dark",           action="store_true", help="take Auto-Dark measurements")
        parser.add_argument("--auto-raman",          action="store_true", help="take Auto-Raman measurements")

        parser.add_argument("--laser-warning-delay-sec", type=int,        help="set laser warning delay (sec)")
        parser.add_argument("--start-line",          type=int,            help="set vertical ROI start line")
        parser.add_argument("--stop-line",           type=int,            help="set vertical ROI stop line")
        parser.add_argument("--power-watchdog-sec",  type=int,            help="set power watchdog (sec)")
        self.args = parser.parse_args()

    async def run(self):

        # connect to device, read device information and characteristics
        await self.connect()

        # read EEPROM
        if self.args.eeprom:
            await self.read_eeprom()

        # timeouts
        if self.args.power_watchdog_sec is not None:
            await self.set_power_watchdog_sec(self.args.power_watchdog_sec)
        if self.args.laser_warning_delay_sec is not None:
            await self.set_laser_warning_delay_sec(self.args.laser_warning_delay_sec)

        # explicit laser control
        if self.args.laser_enable:
            await self.set_laser_enable(self.args.laser_enable)

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
            await self.read_spectra()

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
        await self.read_device_information()

        # get Characteristic information
        await self.read_characteristics()

        elapsed_sec = (datetime.now() - self.start_time).total_seconds()
        self.debug("initial connection took {elapsed_sec:.2f} sec")

    def detection_callback(self, device, advertisement_data):
        """
        discovered device 13874014-5EDA-5E6B-220E-605D00FE86DF: WP-SiG:WP-01791, 
        advertisement_data AdvertisementData(local_name='WP-SiG:WP-01791', 
                                             service_uuids=['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc'], 
                                             tx_power=0, rssi=-67)
        """
        if self.found:
            return

        if (datetime.now() - self.start_time).total_seconds() >= self.args.timeout_sec:
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
                                  timeout=self.args.timeout_sec)
        self.stop_event.set()
        self.debug(f"BleakClient instantiated: {self.client}")

    def stop_scanning(self):
        self.stop_event.set()

    def disconnected_callback(self):
        print("\ndisconnected")

    async def read_device_information(self):
        print(f"address = {self.client.address}")
        print(f"mtu_size = {self.client.mtu_size} bytes")

        self.device_info = {}
        for service in self.client.services:
            if "Device Information" in str(service):
                for char in service.characteristics:
                    name = char.description
                    value = self.decode(await self.client.read_gatt_char(char.uuid))
                    self.device_info[name] = value

        print("Device Information:")
        for k, v in self.device_info.items():
            print(f"  {k:24s} = {v}")

    async def read_characteristics(self):
        # find the primary service
        self.primary_service = None
        for service in self.client.services:
            if service.uuid.lower() == self.WASATCH_SERVICE.lower():
                self.primary_service = service
                
        if self.primary_service is None:
            return

        # iterate over standard Characteristics
        print("Characteristics:")
        for char in self.primary_service.characteristics:
            name = self.get_char_name_by_uuid(char.uuid)
            if "read" in char.properties:
                try:
                    value = await self.client.read_gatt_char(char.uuid)
                    value = self.decode(value)
                    extra = f", Value: {value}"
                except Exception as e:
                    extra = f", Error: {e}"
            else:
                extra = ""

            if "write-without-response" in char.properties:
                extra += f", Max write w/o rsp size: {char.max_write_without_response_size}"

            props = ",".join(char.properties)
            print(f"  Characteristic {name:16s} {char.uuid} ({props}){extra}")

        # @see https://bleak.readthedocs.io/en/latest/api/client.html#gatt-characteristics
        # async BleakClient.read_gatt_char (char_specifier: Union[BleakGATTCharacteristic, int, str, UUID], **kwargs)→ bytearray
        # async BleakClient.write_gatt_char(char_specifier: Union[BleakGATTCharacteristic, int, str, UUID], data: Buffer, response: bool = None)→ None

    async def read_char(self, name, min_len=None):
        uuid = self.get_uuid_by_name(name)
        if uuid is None:
            raise f"invalid characteristic {name}"

        response = await self.client.read_gatt_char(uuid)
        if response is None:
            raise f"characteristic {name} returned no data"

        if min_len is not None and len(response) < min_len:
            raise f"characteristic {name} returned insufficient data ({len(response)} < {min_len})"

        buf = bytearray()
        for byte in response:
            buf.append(byte)
        return buf

    async def write_char(self, name, data, response_len=0):
        uuid = self.get_uuid_by_name(name)
        if uuid is None:
            raise f"invalid characteristic {name}"

        if isinstance(list, data):
            data = bytearray(data)
        response = await self.client.write_gatt_char(uuid, data, response=(response_len > 0))
        if response_len and response is None or len(response) < response_len:
            raise f"characteristic {name} returned insufficient data (response {response} < response_len {response_len})"
        return response

    ############################################################################
    # Timeouts
    ############################################################################

    async def set_power_watchdog_sec(self, sec):
        tier = self.generics.get("SECOND_TIER")
        cmd = self.generics.get("SET_POWER_WATCHDOG_SEC")
        await self.write_char("GENERIC_MESSAGE", [tier, cmd, sec])

    async def set_laser_warning_delay_sec(self, sec):
        cmd = self.generics.get("SET_LASER_WARNING_DELAY_SEC")
        await self.write_char("GENERIC_MESSAGE", [cmd, sec])

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
        data = [ 0x00,               # fixed
                 (ms << 16) & 0xff,  # MSB
                 (ms <<  8) & 0xff,
                 (ms      ) & 0xff ] # LSB
        await self.write_char("INTEGRATION_TIME", data)

    async def set_gain_db(self, db):
        # using dedicated Characteristic, although 2nd-tier version now exists
        msb = int(db) & 0xff
        lsb = int((value - int(value)) * 256) & 0xff
        await self.write_char("GAIN_DB", [msb, lsb])

    async def set_scans_to_average(self, n):
        tier = self.generics.get("SECOND_TIER")
        cmd = self.generics.get("SET_SCANS_TO_AVERAGE")
        await self.write_char("GENERIC_MESSAGE", [tier, cmd, n])

    async def set_start_line(self, n):
        tier = self.generics.get("SECOND_TIER")
        cmd = self.generics.get("SET_START_LINE")
        await self.write_char("GENERIC_MESSAGE", [tier, cmd, n])

    async def set_stop_line(self, n):
        tier = self.generics.get("SECOND_TIER")
        cmd = self.generics.get("SET_STOP_LINE")
        await self.write_char("GENERIC_MESSAGE", [tier, cmd, n])

    ############################################################################
    # Monitor
    ############################################################################

    async def get_battery_state(self):
        buf = await self.read_char("BATTERY_STATUS", 2)
        print(f"battery response: {buf}")
        return { 'perc': 100.0, 
                 'charging': True }

    async def get_laser_state(self):
        buf = await self.read_char("LASER_STATUS", 7)
        return { 'mode':            buf[0],
                 'type':            buf[1],
                 'enable':          buf[2],
                 'watchdog_sec':    buf[3],
                 'mask':            buf[6],
                 'interlock_closed':buf[6] & 0x01,
                 'firing':          buf[6] & 0x02 }

    async def get_status(self):
        bat = await self.get_battery_state()
        bat_perc = f"{bat['perc']:.2f}%%"
        bat_chg = 'charging' if bat['charging'] else 'discharging'

        las = await self.get_laser_state()
        las_firing = las['firing']
        intlock = 'closed (armed)' if las['interlock_closed'] else 'open (safe)'

        return f"Battery {bat_perc} ({bat_chg}), Laser {las_firing}, Interlock {intlock}"

    async def monitor(self):
        while True:
            status = await self.get_status()
            print(f"{datetime.now()} {status}")
            sleep(1)

    ############################################################################
    # Spectra
    ############################################################################

    async def read_spectra(self):
        pass

    ############################################################################
    # EEPROM
    ############################################################################

    async def read_eeprom(self):
        await self.read_eeprom_pages()
        self.parse_eeprom_pages()


    async def read_eeprom_pages(self):
        start_time = datetime.now()

        self.eeprom = {}
        self.eeprom_pages = []

        cmd_uuid = self.get_uuid_by_name("EEPROM_CMD")
        data_uuid = self.get_uuid_by_name("EEPROM_DATA")
        for i in range(8):
            buf = bytearray()
            for j in range(4):
                self.debug(f"writing EEPROM_CMD(page {i}, subpage {j})")
                page_ids = bytearray([i, j])
                await self.client.write_gatt_char(cmd_uuid, page_ids, response = True)

                log.debug("reading EEPROM_DATA")
                response = await self.client.read_gatt_char(data_uuid)
                for byte in response:
                    buf.append(byte)
            pages.append(buf)

        elapsed_sec = (datetime.now() - start_time).total_seconds()
        self.debug("reading eeprom took {elapsed_sec:.2f} sec")

    def parse_eeprom_pages(self):
        for name, field in self.eeprom_field_loc.items():
            self.unpack_eeprom_field(field.pos, field.data_type, name)

        print("EEPROM:")
        for name, value in self.eeprom.items():
            print(f"  {name:30s} {value}")

    def unpack_eeprom_field(self, address, data_type, field):
        page       = address[0]
        start_byte = address[1]
        length     = address[2]
        end_byte   = start_byte + length

        if page > len(self.eeprom_pages):
            print("error unpacking EEPROM page %d, offset %d, len %d as %s: invalid page (field %s)" % ( 
                page, start_byte, length, data_type, field))
            return

        buf = self.eeprom_pages[page]
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
            except:
                print("error unpacking EEPROM page %d, offset %d, len %d as %s" % (page, start_byte, length, data_type))
                return

        # self.debug(f"Unpacked page {page:02d}, offset {start_byte:02d}, len {length:02d}, datatype {data_type}: {unpack_result} {field}")

        self.field_names.append(field)
        self.eeprom[field] = unpack_result

    ############################################################################
    # Utility
    ############################################################################

    def debug(self, msg):
        if self.args.debug:
            print(f"{datetime.now()} DEBUG: {msg}")

    def wrap_uuid(self, code):
        return f"d1a7{code:04x}-af78-4449-a34f-4da1afaf51bc".lower()

    def get_char_name_by_uuid(self, uuid):
        return self.char_name_by_uuid.get(uuid.lower(), None)
        
    def get_char_uuid_by_name(self, name):
        code = self.char_code_by_name.get(name.upper(), None)
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

"""
MacBook-Pro.lan [~/work/code/Python-USB-WP-Raman-Examples/generic] mzieg  4:06PM $ python -u ble-util.py --serial-number WP-01791
2024-10-18 16:06:49.828516 rssi local_name
2024-10-18 16:06:51.426465  -71 WP-SiG:WP-01791
address = 13874014-5EDA-5E6B-220E-605D00FE86DF
mtu_size = 515 bytes
Device Information:
  Manufacturer Name String = Wasatch Photonics
  Hardware Revision String = 4
  Firmware Revision String = 01.4.28
  Software Revision String = 4.7.3
Characteristics:
  Characteristic INTEGRATION_TIME d1a7ff01-af78-4449-a34f-4da1afaf51bc (read,write), Value:
  Characteristic GAIN_DB          d1a7ff02-af78-4449-a34f-4da1afaf51bc (read,write), Value: bytearray(b'\xaf')
  Characteristic LASER_STATE      d1a7ff03-af78-4449-a34f-4da1afaf51bc (read,write,notify), Value:
  Characteristic ACQUIRE_SPECTRUM d1a7ff04-af78-4449-a34f-4da1afaf51bc (write)
  Characteristic SPECTRUM_COMMAND d1a7ff05-af78-4449-a34f-4da1afaf51bc (read,write), Value:
  Characteristic READ_SPECTRUM    d1a7ff06-af78-4449-a34f-4da1afaf51bc (read,write,indicate), Value: bytearray(b'\xff\xff')
  Characteristic EEPROM_COMMAND   d1a7ff07-af78-4449-a34f-4da1afaf51bc (read,write), Value: bytearray(b'\xad')
  Characteristic EEPROM_DATA      d1a7ff08-af78-4449-a34f-4da1afaf51bc (read,indicate), Value: bytearray(b'\xe1')
  Characteristic BATTERY_STATUS   d1a7ff09-af78-4449-a34f-4da1afaf51bc (read,notify), Value:
  Characteristic GENERIC_MESSAGE  d1a7ff0a-af78-4449-a34f-4da1afaf51bc (read,write,indicate), Value:
"""
