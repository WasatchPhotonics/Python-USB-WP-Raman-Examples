#!/usr/bin/env python -u

import sys
import usb.core
import time
import numpy as np
import matplotlib.pyplot as plt

H2D = 0x40
D2H = 0xC0
BUFFER_SIZE = 8
Z = [0] * BUFFER_SIZE
TIMEOUT = 1000
MAX_SEC = 1000
INTEG_MS = 1000

PIXELS = 1024
LINES = 70
LINE_LEN = PIXELS * 2

MARKER = 0xffff
CLAMP  = 0xfffe

class Fixture:
    """
    0xeb = AREA_SCAN_ENABLE
    0xa6 = LINE_COUNT
    0xa8 = LINE_INTERVAL
    """

    def __init__(self):
        self.extra = []
        self.line_count = 0
        self.frame_count = 0
        self.total_line_count = 0

        self.frame = [ [0] * PIXELS for line in range(LINES) ] # 70 lines, each of 1024 pixels

    def connect(self):
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
        return self.dev is not None

    def send_trigger(self):
        print("sending ACQUIRE software trigger...")
        self.dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT) 

    def get_spectrum(self):
        data = self.extra # start with any extra data we might have picked up on the last read
        self.extra = []

        while len(data) < LINE_LEN:
            bytes_remaining = LINE_LEN - len(data)
            latest_data = self.dev.read(0x82, bytes_remaining, timeout=TIMEOUT)
            # print(f"read {len(latest_data)} bytes ({bytes_remaining} requested)")
            data.extend(latest_data) 

        extra_len = len(data) - LINE_LEN
        if extra_len > 0:
            print(f"WARNING: storing {extra_len} extra bytes toward the next line")
            self.extra = line_data[LINE_LEN:]

        # demarshal line into spectrum
        spectrum = []
        for i in range(PIXELS):
            lsb = data[i*2 + 0]
            msb = data[i*2 + 1]
            intensity = (msb << 8) + lsb
            spectrum.append(intensity)

        self.total_line_count += 1
        return spectrum
    
    def set_integration_time_ms(self, ms):
        print(f"setting integration time to {ms}ms")
        self.dev.ctrl_transfer(H2D, 0xb2, ms, 0, Z, TIMEOUT) 

    def set_area_scan_enable(self, flag):
        print(f"area scan enable = {flag}")
        self.dev.ctrl_transfer(H2D, 0xeb, 1 if flag else 0, 0, Z, TIMEOUT) 

    def eat_throwaways(self):
        count = 0
        try:
            while True:
                throwaway = self.get_spectrum()
                print(f"consumed throwaway {count}: {throwaway[:5]}")
                count += 1
        except usb.core.USBTimeoutError:
            pass

        if count == 0:
            print("no throwaways to consume")
        else:
            print(f"consumed {count} throwaways")

    def display_frame(self):
        image = np.array(self.frame)

        sums = image.sum(axis=1)
        normalized = image / sums[:, np.newaxis]

        plt.imshow(normalized, cmap='gray') 
        plt.title(f"Frame {self.frame_count}")
        plt.show(block=False)
        plt.pause(3)
        time.sleep(1)

    def run(self):
        self.set_integration_time_ms(100)

        print("eating initial throwawys (no ACQUIRE)")
        self.eat_throwaways()

        print("sending one ACQUIRE, then eating throwaways")
        self.send_trigger()
        self.eat_throwaways()

        # enable area scan
        print("enabling area scan, then eating throwaways")
        self.set_area_scan_enable(True)
        self.eat_throwaways()

        # ready to start reading frames of area scan data
        while True:
            # request a frame
            self.send_trigger()

            for line in range(LINES):
                prefix = f"line {self.line_count}, frame {self.frame_count}, total {self.total_line_count}"
                spectrum = self.get_spectrum()

                # first pixel is start-of-line marker
                if spectrum[0] != MARKER:
                    print(f"{prefix}: WARNING: first pixel expected 0x{MARKER:04x}, found 0x{spectrum[0]:04x}")

                # verify rest of line is clamped to 0xfffe
                for i, intensity in enumerate(spectrum):
                    if i > 1 and spectrum[i] > CLAMP:
                        print(f"{prefix}: WARNING: pixel {i:4d} value 0x{spectrum[i]:04x} exceeds clamp 0x{CLAMP:04x}")

                # second pixel is line index
                line_index = spectrum[1]
                if line_index >= LINES:
                    print(f"{prefix}: WARNING: line_index {line_index} exceeds frame limit")
                else:
                    # store line in image
                    self.frame[line_index] = spectrum
                    print(f"{prefix}: stored line {line_index}: {spectrum[:5]}")
                
                # periodically display image
                self.line_count += 1
                if line_index + 1 == LINES:
                    print(f"{prefix}: displaying frame {self.frame_count}")

                    self.display_frame()

                    # initialize for next frame
                    self.line_count = 0
                    self.frame_count += 1
                    print(f"\nreading frame {self.frame_count}")

if __name__ == "__main__":
    fixture = Fixture()
    if not fixture.connect():
        sys.exit(-1)
    fixture.run()
