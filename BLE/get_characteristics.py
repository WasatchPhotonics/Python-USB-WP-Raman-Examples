import bleak
import asyncio

async def main():
    print("Scanning for devices...")
    devices = await bleak.discover()
    print("Bluetooth Address".ljust(len(str(devices[0].address))+3) + "| Device Name")
    print("\n".join([f"{idx}) "+str(d) for idx, d in enumerate(devices)]))

    device_num = input("\nChoose a device:")
    try:
        device_num = int(device_num)
    except:
        print("Couldn't parse int. Please choose an integer.")
        return

    selected_device = devices[device_num]
    client = bleak.BleakClient(selected_device.address)
    await client.connect()
    services = await client.get_services()
    chars = [s.characteristics for s in list(services)]
    service_chars = zip(services, chars)
    print("\n".join([str(s) + "\nCharacteristics:\n" + "\n".join([str(ch) for ch in c]) for s,c in service_chars]))

asyncio.run(main())