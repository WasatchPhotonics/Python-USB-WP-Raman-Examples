#!/usr/bin/env python -u

import sys
import usb.core
import time
import numpy as np
import argparse
import matplotlib.pyplot as plt
import matplotlib.image

from datetime import datetime

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

    def __init__(self):
        self.extra = []
        self.line_count = 0
        self.frame_count = 0
        self.total_line_count = 0

        self.args = self.parse_args()

        self.frame = [ [0] * PIXELS for line in range(LINES) ] # 70 lines, each of 1024 pixels

    def parse_args(self):
        parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument("--debug",               action="store_true", help="debug output")
        parser.add_argument("--integration-time-ms", type=int,            help="set integration time", default=100)
        parser.add_argument("--frames",              type=int,            help="how many frames to collect (0=infinite)", default=5)
        parser.add_argument("--line-count",          type=int,            help="set line count")
        parser.add_argument("--line-interval",       type=int,            help="set line interval")
        parser.add_argument("--plot",                action="store_true", help="graph frames")
        parser.add_argument("--save",                action="store_true", help="save frames as PNG")
        return parser.parse_args()

    def connect(self):
        self.dev = usb.core.find(idVendor=0x24aa, idProduct=0x1000)
        return self.dev is not None

    def debug(self, msg):
        if self.args.debug:
            print(f"{datetime.now()} DEBUG: {msg}")

    def send_trigger(self):
        self.debug("sending ACQUIRE software trigger...")
        self.dev.ctrl_transfer(H2D, 0xad, 0, 0, Z, TIMEOUT) 

    def get_spectrum(self):
        data = self.extra # start with any extra data we might have picked up on the last read
        self.extra = []

        while len(data) < LINE_LEN:
            bytes_remaining = LINE_LEN - len(data)
            latest_data = self.dev.read(0x82, bytes_remaining, timeout=TIMEOUT)
            self.debug(f"read {len(latest_data)} bytes ({bytes_remaining} requested): {latest_data[:10]}")
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
        self.debug(f"setting integration time to {ms}ms")
        self.dev.ctrl_transfer(H2D, 0xb2, ms, 0, Z, TIMEOUT) 

    def set_area_scan_enable(self, flag):
        self.debug(f"area scan enable = {flag}")
        self.dev.ctrl_transfer(H2D, 0xeb, 1 if flag else 0, 0, Z, TIMEOUT) 

    def set_area_scan_line_count(self, n):
        self.debug(f"setting line count to {n}")
        self.dev.ctrl_transfer(H2D, 0xa6, n, 0, Z, TIMEOUT) 

    def set_area_scan_line_interval(self, n):
        self.debug(f"setting line interval to {n}")
        self.dev.ctrl_transfer(H2D, 0xa8, n, 0, Z, TIMEOUT) 

    def eat_throwaways(self):
        count = 0
        try:
            while True:
                throwaway = self.get_spectrum()
                self.debug(f"consumed throwaway {count}: {throwaway[:5]}")
                count += 1
        except usb.core.USBTimeoutError:
            pass

        if count == 0:
            self.debug("no throwaways to consume")
        else:
            print(f"WARNING: consumed {count} throwaways")

    def process_frame(self):
        if not (self.args.plot or self.args.save):
            return

        image = np.array(self.frame)
        sums = image.sum(axis=1)
        normalized = image / sums[:, np.newaxis]
        scaled = normalized * 65535

        if self.args.save:
            filename = f"areascan-{self.frame_count:03d}.png"
            matplotlib.image.imsave(filename, scaled)
            self.debug("saved {filename}")

        if self.args.plot:
            plt.imshow(scaled, cmap='gray') 
            plt.title(f"Frame {self.frame_count}")
            plt.show(block=False)
            plt.pause(1)
            # time.sleep(1)

    def run(self):
        self.set_integration_time_ms(self.args.integration_time_ms)

        if self.args.line_count is not None:
            self.set_area_scan_line_count(self.args.line_count)

        if self.args.line_interval is not None:
            self.set_area_scan_line_interval(self.args.line_interval)

        self.debug("eating initial throwawys (no ACQUIRE)")
        self.eat_throwaways()

        self.debug("sending one ACQUIRE, then eating throwaways")
        self.send_trigger()
        self.eat_throwaways()

        try:
            self.debug("enabling area scan, then eating throwaways")
            self.set_area_scan_enable(True)
            self.eat_throwaways()

            while self.frame_count < self.args.frames or 0 == self.args.frames:
                # request a frame
                self.send_trigger()

                for line in range(LINES):
                    prefix = f"line {self.line_count}, frame {self.frame_count}, total {self.total_line_count}"
                    spectrum = self.get_spectrum()

                    # first pixel is start-of-line marker
                    if spectrum[0] != MARKER:
                        print(f"{prefix}: WARNING: first pixel expected 0x{MARKER:04x}, found 0x{spectrum[0]:04x}")
                    spectrum[0] = spectrum[2] # stomp

                    # verify rest of line is clamped to 0xfffe
                    for i, intensity in enumerate(spectrum):
                        if i > 1 and spectrum[i] > CLAMP:
                            print(f"{prefix}: WARNING: pixel {i:4d} value 0x{spectrum[i]:04x} exceeds clamp 0x{CLAMP:04x}")

                    # second pixel is line index
                    line_index = spectrum[1]
                    if line_index >= LINES:
                        print(f"{prefix}: WARNING: line_index {line_index} exceeds frame limit")
                    spectrum[1] = spectrum[2] # stomp

                    # store line in image
                    self.frame[line_index] = spectrum
                    self.debug(f"{prefix}: stored line {line_index}: {spectrum[:5]}")
                    
                    # process completed frame
                    self.line_count += 1
                    if line_index + 1 == LINES:
                        self.debug(f"{prefix}: displaying frame {self.frame_count}")
                        self.process_frame()

                        # initialize for next frame
                        self.line_count = 0
                        self.frame_count += 1
                        self.debug(f"\nreading frame {self.frame_count}")
        except:
            self.set_area_scan_enable(False)
            
if __name__ == "__main__":
    fixture = Fixture()
    if not fixture.connect():
        print("No spectrometer found.")
        sys.exit(-1)
    fixture.run()
