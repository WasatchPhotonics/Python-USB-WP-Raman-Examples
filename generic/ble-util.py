import argparse
import asyncio
from bleak import BleakScanner, BleakClient
from datetime import datetime

class Fixture:
    WASATCH_SERVICE = "D1A7FF00-AF78-4449-A34F-4DA1AFAF51BC"

    def __init__(self):
        self.stop_event = asyncio.Event()
        self.client = None
        self.found = False
        self.start_time = None

        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--timeout-sec",         type=int,            help="how long to search for spectrometers", default=30)
        parser.add_argument("--serial-number",       type=str,            help="delay n ms between spectra")
        self.args = parser.parse_args()

    def stop_scanning(self):
        self.stop_event.set()

    def dump(self, device, adv_data):
        print("==> Device:")
        for attr in ['name', 'address', 'details']:
            if hasattr(device, attr):
                value = getattr(device, attr)
                print(f"  {attr} = {value}")
        print("==> Advertising Data:")
        for attr in ['local_name', 'manufacturer_data', 'platform_data', 'rssi', 'service_data', 'service_uuids', 'tx_power']:
            if hasattr(adv_data, attr):
                value = getattr(adv_data, attr)
                print(f"  {attr} = {value}")
        print("")

    def debug(self, msg):
        if self.args.debug:
            print(f"DEBUG: {msg}")

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

        print(f"{advertisement_data.rssi:4d} [{advertisement_data.local_name}]")
        if self.args.serial_number is None:
            return # we're just listing

        if self.args.serial_number.lower() not in advertisement_data.local_name.lower():
            return # not the one

        # don't stop the scanner just yet, but ignore subsequent discoveries
        self.found = True

        print(f"instantiating BleakClient")
        self.client = BleakClient(address_or_ble_device = device, 
                                  timeout = 30)

        print(f"BleakClient instantiated: {self.client}")

        self.stop_event.set()

    async def main(self):

        self.start_time = datetime.now()
        print("rssi local_name")
        async with BleakScanner(detection_callback=self.detection_callback, service_uuids=[self.WASATCH_SERVICE]) as scanner:
            await self.stop_event.wait()

        # scanner stops when block exits
        self.debug("stopping")

fixture = Fixture()
asyncio.run(fixture.main())

"""
discovered device 13874014-5EDA-5E6B-220E-605D00FE86DF: WP-SiG:WP-01791, advertising_data AdvertisementData(local_name='WP-SiG:WP-01791', service_uuids=['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc'], tx_power=0, rssi=-67)
==> Device:
  name = WP-SiG:WP-01791
  address = 13874014-5EDA-5E6B-220E-605D00FE86DF
  details = (<CBPeripheral: 0x6000022a4410, identifier = 13874014-5EDA-5E6B-220E-605D00FE86DF, name = WP-SiG:WP-01791, mtu = 0, state = disconnected>, <CentralManagerDelegate: 0x7f8833739fc0>)
==> Advertising Data:
  local_name = WP-SiG:WP-01791
  manufacturer_data = {}
  platform_data = (<CBPeripheral: 0x6000022a4410, identifier = 13874014-5EDA-5E6B-220E-605D00FE86DF, name = WP-SiG:WP-01791, mtu = 0, state = disconnected>, {
    kCBAdvDataIsConnectable = 1;
    kCBAdvDataLocalName = "WP-SiG:WP-01791";
    kCBAdvDataRxPrimaryPHY = 0;
    kCBAdvDataRxSecondaryPHY = 0;
    kCBAdvDataServiceUUIDs =     (
        FF00,
        "D1A7FF00-AF78-4449-A34F-4DA1AFAF51BC"
    );
    kCBAdvDataTimestamp = "750965034.823734";
    kCBAdvDataTxPowerLevel = 0;
}, -67)
  rssi = -67
  service_data = {}
  service_uuids = ['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc']
  tx_power = 0


instantiating BleakClient
BleakClient instantiated: BleakClient, 13874014-5EDA-5E6B-220E-605D00FE86DF
discovered device 13874014-5EDA-5E6B-220E-605D00FE86DF: WP-SiG:WP-01791, advertising_data AdvertisementData(local_name='WP-SiG:WP-01791', service_uuids=['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc'], tx_power=0, rssi=-67)
==> Device:
  name = WP-SiG:WP-01791
  address = 13874014-5EDA-5E6B-220E-605D00FE86DF
  details = (<CBPeripheral: 0x6000022a4410, identifier = 13874014-5EDA-5E6B-220E-605D00FE86DF, name = WP-SiG:WP-01791, mtu = 0, state = disconnected>, <CentralManagerDelegate: 0x7f8833739fc0>)
==> Advertising Data:
  local_name = WP-SiG:WP-01791
  manufacturer_data = {}
  platform_data = (<CBPeripheral: 0x6000022a4410, identifier = 13874014-5EDA-5E6B-220E-605D00FE86DF, name = WP-SiG:WP-01791, mtu = 0, state = disconnected>, {
    kCBAdvDataIsConnectable = 1;
    kCBAdvDataLeBluetoothDeviceAddress = {length = 7, bytes = 0x2eea020860f401};
    kCBAdvDataLocalName = "WP-SiG:WP-01791";
    kCBAdvDataRxPrimaryPHY = 0;
    kCBAdvDataRxSecondaryPHY = 0;
    kCBAdvDataServiceUUIDs =     (
        FF00,
        "D1A7FF00-AF78-4449-A34F-4DA1AFAF51BC"
    );
    kCBAdvDataTimestamp = "750965034.823804";
    kCBAdvDataTxPowerLevel = 0;
}, -67)
  rssi = -67
  service_data = {}
  service_uuids = ['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc']
  tx_power = 0


instantiating BleakClient
BleakClient instantiated: BleakClient, 13874014-5EDA-5E6B-220E-605D00FE86DF
*** stopping
"""
