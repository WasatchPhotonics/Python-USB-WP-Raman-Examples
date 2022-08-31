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
    chars = [filter(lambda c: "read" in c.properties, ch) for ch in chars]
    service_chars = zip(services, chars)
    idx = 0
    list_output = []
    char_options = {}
    for s, c in service_chars:
        list_output.append(str(s) + "\nCharacteristics:\n")
        for ch in c:
            list_output.append(f"{idx}) {str(ch)}")
            char_options[idx] = ch
            idx += 1
    print("\n".join(list_output))
    while True:
        selected_read = input("choose a characteristic to read (type non int to quit): ")
        try:
            selected_read = int(selected_read)
        except:
            print("Couldn't parse int. Please choose an integer.")
            return
        result = await client.read_gatt_char(char_options[selected_read])
        print(result)


asyncio.run(main())

