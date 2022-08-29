import bleak
import asyncio

async def main():
    print("Scanning for devices...")
    devices = await bleak.discover()
    print("Bluetooth Address".ljust(len(str(devices[0].address))) + "| Device Name")
    print("\n".join([str(d) for d in devices]))

asyncio.run(main())
