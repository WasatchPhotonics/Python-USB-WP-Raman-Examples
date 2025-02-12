import random
import platform
import usb.core

from time import sleep
from datetime import datetime

if platform.system() == "Darwin":
    import usb.backend.libusb1 as backend
else:
    import usb.backend.libusb0 as backend

HOST_TO_DEVICE = 0x40
DEVICE_TO_HOST = 0xC0
TIMEOUT_MS = 1000

class Fixture:

    def __init__(self):
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=0x4000, backend=backend.get_backend())
        if not self.dev:
            print("no spectrometers found")
            return

    def run(self):
        if not self.dev:
            return

        while True:
            print()
            for i in range(5):
                amb_temp = self.get_amb_temp()
                bat_stat = self.get_bat_stat()
                print(f"{datetime.now()} ambient temperature {amb_temp}, battery status {bat_stat}")
                sleep(1)

            response = input("\nEnter choice (1=read laser temp, 2=change TEC mode, 3=quit, anything else continue): ")
            if "1" in response:
                las_temp = self.get_las_temp()
                print(f"{datetime.now()} laser temperature {las_temp}")
            if "2" in response:
                mode = random.randint(0, 3)
                self.set_laser_tec_mode(mode)
            if "3" in response:
                break

    def get_amb_temp(self):
        value = self.get_cmd(0xff, 0x2a, label="GET_AMBIENT_TEMPERATURE_DEGC_ARM", msb_len=1)
        print("Ambient Temp {} Deg C".format(value))
        return f"{value:3d}°C"

    def get_bat_stat(self):
        word = self.get_cmd(0xff, 0x13, label="GET_BATTERY_STATE", msb_len=3)
        charging = 'charging' if (word & 0xff) else 'discharging'
        lsb = (word >> 16) & 0xff
        msb = (word >>  8) & 0xff
        perc = msb + (1.0 * lsb / 256.0)
        return f"{perc:6.2f}% ({charging})"

    def get_las_temp(self):
        data = self.get_cmd(0xd5, length=2, label="GET_ADC", lsb_len=2)
        raw = data & 0xfff

        # conversion for 220250 Rev4 MAX1978ETM-T 3V3 buffer -> 12-bit DAC -> degC
        degC = 0
        coeffs = [ 1.5712971947853123e+000, 1.4453391889061071e-002, -1.8534086153440592e-006, 4.2553356470494626e-010 ]
        for i, coeff in enumerate(coeffs):
            degC += coeff * pow(raw, i)
        return f"{degC:6.2f}°C"

    def set_laser_tec_mode(self, mode):
        print(f"setting laser TEC mode {mode}")
        self.send_cmd(0x84, mode, label="SET_LASER_TEC_MODE", debug=True)

    def send_cmd(self, cmd, value=0, index=0, buf=None, label=None, debug=False):
        if buf is None:
            if self.dev.idProduct == 0x4000:
                buf = [0] * 8
            else:
                buf = ""
        if debug: 
            print("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x) >> %s %s" % (HOST_TO_DEVICE, cmd, value, index, buf, label))
        self.dev.ctrl_transfer(HOST_TO_DEVICE, cmd, value, index, buf, TIMEOUT_MS)

    def get_cmd(self, cmd, value=0, index=0, length=64, lsb_len=None, msb_len=None, label=None, debug=False):
        if debug:
            print("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d)" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS))
        result = self.dev.ctrl_transfer(DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS)
        if debug:
            print("ctrl_transfer(0x%02x, 0x%02x, 0x%04x, 0x%04x, len %d, timeout %d) << %s" % (DEVICE_TO_HOST, cmd, value, index, length, TIMEOUT_MS, result))

        if result is None:
            print(f"ERROR: received None from {label} (expected lsb_len {lsb_len}, msb_len {msb_len})")
            return 0

        if lsb_len is not None and len(result) != lsb_len:
            print(f"ERROR: received insufficient response for {label}: (expected lsb_len {lsb_len}, got {len(result)})")
            return 0

        if msb_len is not None and len(result) != msb_len:
            print(f"ERROR: received insufficient response for {label}: (expected msb_len {msb_len}, got {len(result)})")
            return 0

        value = 0
        if msb_len is not None:
            for i in range(msb_len):
                value = value << 8 | result[i]
            return value
        elif lsb_len is not None:
            for i in range(lsb_len):
                value = (result[i] << (8 * i)) | value
            return value
        else:
            return result

fixture = Fixture()
fixture.get_amb_temp()
#fixture.run()
