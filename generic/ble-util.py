import asyncio
from bleak import BleakScanner, BleakClient

async def main():
    stop_event = asyncio.Event()

    def dump(device, adv_data):
        print("Device:")
        for attr in ['name', 'address', 'details']:
            if hasattr(device, attr):
                value = getattr(device, attr)
                print(f"  {attr} = {value}")
        print("Advertising Data:")
        for attr in ['local_name', 'manufacturer_data', 'platform_data', 'rssi', 'service_data', 'service_uuids', 'tx_power']:
            if hasattr(adv_data, attr):
                value = getattr(adv_data, attr)
                print(f"  {attr} = {value}")

    def discover_callback(device, advertising_data):
        # discovered device 13874014-5EDA-5E6B-220E-605D00FE86DF: WP-SiG:WP-01791, 
        # advertising_data AdvertisementData(local_name='WP-SiG:WP-01791', 
        #                                    service_uuids=['0000ff00-0000-1000-8000-00805f9b34fb', 'd1a7ff00-af78-4449-a34f-4da1afaf51bc'], 
        #                                    tx_power=0, rssi=-67)
        print(f"discovered device {device}, advertising_data {advertising_data}")
        if not hasattr(advertising_data, "local_name") or advertising_data.local_name is None:
            return

        dump(device, advertising_data)

        if "wp-sig" in advertising_data.local_name.lower():
            print(f"instantiating BleakClient")
            client = BleakClient(address_or_ble_device = device, 
                                      timeout = 30)

            print(f"BleakClient instantiated: {client}")
            stop_event.set()

    async with BleakScanner(discover_callback) as scanner:
        print("scanning")
        await stop_event.wait()

    # scanner stops when block exits
    print("stopping")

asyncio.run(main())
