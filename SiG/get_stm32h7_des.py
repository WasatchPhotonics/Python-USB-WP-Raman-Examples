import sys
import usb.core

from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUF             = [0] * 8
TIMEOUT_MS      = 1000

PIXELS = 1952
COUNT  = 10

print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("No matching spectrometer found")
    sys.exit(1)

print("requesting SC_GET_CPU_UNIQUE_DEV_ID")
data = dev.ctrl_transfer(DEVICE_TO_HOST, 0xff, 0x2c, 0, 12, TIMEOUT_MS)
print(f"<< {data}")
if len(data) != 12:
    print("expected 12 bytes (received {len(data)})")
    sys.exit(1)


des = "-".join(f"{v:02x}" for v in data) # Device Electronic Signature
print(f"STM32H7 DES is {des}")

# there seems to be structure here...just guessing.
# @see https://www.st.com/content/ccc/resource/training/technical/product_training/group0/fe/68/44/22/f6/ff/45/77/STM32H7-System-DeviceElectronicSignature_DES/files/STM32H7-System-DeviceElectronicSignature_DES.pdf/_jcr_content/translations/en.STM32H7-System-DeviceElectronicSignature_DES.pdf
#
# first6 = data[:6]
# last6  = data[6:]
# first = "".join(chr(v) for v in first6)
# last = "".join(f"{v:02x}" for v in last6)
# print(f"parsed: {last}-{first}")
