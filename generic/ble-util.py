import argparse
import asyncio
from bleak import BleakScanner, BleakClient
from datetime import datetime

class Fixture:
    WASATCH_SERVICE   = "D1A7FF00-AF78-4449-A34F-4DA1AFAF51BC"
    DISCOVERY_SERVICE = "0000ff00-0000-1000-8000-00805f9b34fb"

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
        parser.add_argument("--laser-enable",        action="store_true", help="fire the laser")
        parser.add_argument("--max-sec",             type=int,            help="how long to perform the test", default=5)
        self.args = parser.parse_args()

    def wrap_uuid(self, code):
        return f"d1a7{code:04x}-af78-4449-a34f-4da1afaf51bc".lower()

    def get_char_name_by_uuid(self, uuid):
        return self.char_name_by_uuid.get(uuid.lower(), None)
        
    def get_char_uuid(self, name):
        name = name.upper()
        if name not in self.char_code_by_name:
            return
        return self.wrap_uuid(self.characteristics[name])

    def stop_scanning(self):
        self.stop_event.set()

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

    def debug(self, msg):
        if self.args.debug:
            print(f"{datetime.now()} DEBUG: {msg}")

    def is_xs(self, device, advertisement_data=None):
        if device is None:
            return
        elif advertisement_data is not None:
            return self.WASATCH_SERVICE.lower() in advertisement_data.service_uuids
        else:
            return "wp-" in device.name.lower()

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

    def disconnected_callback(self):
        print("\ndisconnected")

    async def main(self):

        self.start_time = datetime.now()
        print(f"{datetime.now()} rssi local_name")
        async with BleakScanner(detection_callback=self.detection_callback, service_uuids=[self.WASATCH_SERVICE]) as scanner:
            await self.stop_event.wait()

        # scanner stops when block exits
        self.debug("scanner stopped")

        if self.client:
            await self.test_client()

    def decode(self, data):
        try:
            if isinstance(data, bytearray):
                return data.decode('utf-8')
        except:
            pass
            return data

    async def get_device_information(self):
        self.device_info = {}
        for service in self.client.services:
            if "Device Information" in str(service):
                for char in service.characteristics:
                    name = char.description
                    value = self.decode(await self.client.read_gatt_char(char.uuid))
                    self.device_info[name] = value

    async def test_client(self):
        print(f"address = {self.client.address}")
        print(f"mtu_size = {self.client.mtu_size} bytes")

        # 0x2a26 Firmware Version   STM32 Version (e.g. "1.0.43.2")
        # 0x2a27 Hardware Revision  FPGA Version (e.g. "01.4.28")
        # 0x2a28 Software Version   BL652 Version (e.g. "4.8.5")
        # 0x2a29 Manufacturer Name  "Wasatch Photonics"

        await self.client.connect()

        # grab device information
        await self.get_device_information()
        print("Device Information:")
        for k, v in self.device_info.items():
            print(f"  {k:24s} = {v}")

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

fixture = Fixture()
asyncio.run(fixture.main())

"""
Service d1a7ff00-af78-4449-a34f-4da1afaf51bc (Handle: 11): Unknown
  Characteristic d1a7ff01-af78-4449-a34f-4da1afaf51bc (Handle: 12): Unknown (read,write) , Value:
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 14): Characteristic User Description, Value: Integration Time
  Characteristic d1a7ff02-af78-4449-a34f-4da1afaf51bc (Handle: 15): Unknown (read,write) , Value: bytearray(b'\xaf')
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 17): Characteristic User Description, Value: Gain
  Characteristic d1a7ff03-af78-4449-a34f-4da1afaf51bc (Handle: 18): Unknown (read,write,notify) , Value:

    Descriptor 00002902-0000-1000-8000-00805f9b34fb (Handle: 20): Client Characteristic Configuration, Value:
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 21): Characteristic User Description, Value: Laser Enable
  Characteristic d1a7ff04-af78-4449-a34f-4da1afaf51bc (Handle: 22): Unknown (write)
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 24): Characteristic User Description, Value: Acquire Spectrum
  Characteristic d1a7ff05-af78-4449-a34f-4da1afaf51bc (Handle: 25): Unknown (read,write) , Value:
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 27): Characteristic User Description, Value: Spectrum Command
  Characteristic d1a7ff06-af78-4449-a34f-4da1afaf51bc (Handle: 28): Unknown (read,write,indicate) , Value: bytearray(b'\xff\xff')
    Descriptor 00002902-0000-1000-8000-00805f9b34fb (Handle: 30): Client Characteristic Configuration, Value:
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 31): Characteristic User Description, Value: Read Spectrum
  Characteristic d1a7ff07-af78-4449-a34f-4da1afaf51bc (Handle: 32): Unknown (read,write) , Value: bytearray(b'\xad')
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 34): Characteristic User Description, Value: EEPROM Command
  Characteristic d1a7ff08-af78-4449-a34f-4da1afaf51bc (Handle: 35): Unknown (read,indicate) , Value: bytearray(b'\xe1')
    Descriptor 00002902-0000-1000-8000-00805f9b34fb (Handle: 37): Client Characteristic Configuration, Value:
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 38): Characteristic User Description, Value: EEPROM Data
  Characteristic d1a7ff09-af78-4449-a34f-4da1afaf51bc (Handle: 39): Unknown (read,notify) , Value:

    Descriptor 00002902-0000-1000-8000-00805f9b34fb (Handle: 41): Client Characteristic Configuration, Value:
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 42): Characteristic User Description, Value: Battery Status
  Characteristic d1a7ff0a-af78-4449-a34f-4da1afaf51bc (Handle: 43): Unknown (read,write,indicate) , Value:
    Descriptor 00002902-0000-1000-8000-00805f9b34fb (Handle: 45): Client Characteristic Configuration, Value:
    Descriptor 00002901-0000-1000-8000-00805f9b34fb (Handle: 46): Characteristic User Description, Value: Generic
Service 0000180a-0000-1000-8000-00805f9b34fb (Handle: 47): Device Information
  Characteristic 00002a29-0000-1000-8000-00805f9b34fb (Handle: 48): Manufacturer Name String (read) , Value: Wasatch Photonics
  Characteristic 00002a27-0000-1000-8000-00805f9b34fb (Handle: 50): Hardware Revision String (read) , Value: 4
  Characteristic 00002a26-0000-1000-8000-00805f9b34fb (Handle: 52): Firmware Revision String (read) , Value: 01.4.28
  Characteristic 00002a28-0000-1000-8000-00805f9b34fb (Handle: 54): Software Revision String (read) , Value: 4.7.3
"""
