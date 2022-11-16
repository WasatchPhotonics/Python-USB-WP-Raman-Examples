import bleak
import asyncio


ACQUIRE_CMD = "0xD1A7FF04-AF78-4449-A34F-4DA1AFAF51BC"
SPECTRUM_CMD = "0xD1A7FF05-AF78-4449-A34F-4DA1AFAF51BC"
READ_CMD = "0xD1A7FF06-AF78-4449-A34F-4DA1AFAF51BC"


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
    px_start = 10
    async with bleak.BleakClient(selected_device.address) as client:
        print("telling device to acquire")
        await client.write_gatt_char(ACQUIRE_CMD, b"0x01")

        print(f"setting px start to {px_start}")
        await client.write_gatt_char(SPECTRUM_CMD, px_start.to_bytes(2, "big"))

        print("attempting to get pixel values")
        response = await client.write_gatt_char(READ_CMD, px_start.to_bytes(2, "big"))

        print(f"for read request got response {response}")

asyncio.run(main())