import argparse
import asyncio
from bleak import BleakScanner, BleakClient
from datetime import datetime

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
        self.start_time = None

        self.char_code_by_name = { "INTEGRATION_TIME":   0xff01, 
                                   "GAIN_DB":            0xff02,
                                   "LASER_STATE":        0xff03,
                                   "ACQUIRE_SPECTRUM":   0xff04,
                                   "SPECTRUM_COMMAND":   0xff05,
                                   "READ_SPECTRUM":      0xff06,
                                   "EEPROM_COMMAND":     0xff07,
                                   "EEPROM_DATA":        0xff08,
                                   "BATTERY_STATUS":     0xff09,
                                   "GENERIC_MESSAGE":    0xff0a }

        self.char_name_by_uuid = {}
        for name, code in self.char_code_by_name.items():
            self.char_name_by_uuid[self.wrap_uuid(code)] = name

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--timeout-sec",         type=int,            help="how long to search for spectrometers", default=30)
        parser.add_argument("--serial-number",       type=str,            help="delay n ms between spectra")

        # not yet implemented
        parser.add_argument("--laser-enable",        action="store_true", help="fire the laser")
        parser.add_argument("--read-eeprom",         action="store_true", help="load and parse the EEPROM")
        parser.add_argument("--scan-averaging",      type=int,            help="set scans to average", default=1)
        parser.add_argument("--integration-time-ms", type=int,            help="set integration time", default=400)
        parser.add_argument("--gain-db",             type=float,          help="set gain (dB)", default=8)
        parser.add_argument("--spectra",             type=int,            help="spectra to acquire", default=5)
        parser.add_argument("--outfile",             type=str,            help="save spectra to CSV file")
        parser.add_argument("--monitor",             action="store_true", help="monitor battery, laser state etc")
        self.args = parser.parse_args()

    async def main(self):
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
        await self.get_device_information()

        # get Characteristic information
        await self.get_characteristics()

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

    async def get_device_information(self):
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

    async def get_characteristics(self):
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
        
    def get_char_uuid(self, name):
        name = name.upper()
        if name not in self.char_code_by_name:
            return
        return self.wrap_uuid(self.characteristics[name])

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

fixture = Fixture()
asyncio.run(fixture.main())

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
