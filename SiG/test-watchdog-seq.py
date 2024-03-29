#!/usr/bin/env python

import os
import sys
import usb.core
import platform
from datetime import datetime, timedelta
from time import sleep

VID             = 0x24aa
PID             = 0x4000
HOST_TO_DEVICE  = 0x40
DEVICE_TO_HOST  = 0xC0
BUFFER_SIZE     = 8
BUF             = [0] * BUFFER_SIZE
TIMEOUT_MS      = 1000

class TestFixture:

    def __init__(self):

        print("searching for spectrometer with VID 0x%04x, PID 0x%04x" % (VID, PID))
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is None:
            print("No matching spectrometer found")
            sys.exit(1)

        if os.name == "posix":
            dev.set_configuration()
            usb.util.claim_interface(dev, 0)

        self.dev = dev

    def run(self):
        fw_ver = self.get_firmware_version()
        fpga_ver = self.get_fpga_version()
        print(f"firmware version: {fw_ver}")
        print(f"FPGA version: {fpga_ver}\n")

        # fire the laser for 5 of 10sec, leave "enabled" (but not firing due to timeout)
        self.set_laser_watchdog(5)
        self.fire_laser(sec=10, disable=False)

        # see what happens when changing the watchdog from 5 to 4sec 
        input("\nWe are about to change the laser watchdog to 4sec.  Prepare to observe the laser state.")
        self.set_laser_watchdog(4)
        input("\nObserve laser state, then press <enter> to disable the laser.")

        # formally turn off the laser
        self.set_laser_enable(False)

    def fire_laser(self, sec, disable=True):
        print(f"\nReady to fire the laser for {sec} seconds? ", end='')
        if not disable:
            print("\n*** THE LASER WILL NOT BE DISABLED AFTER FIRING! ***")
        input("(ctrl-C to cancel)")

        self.set_laser_enable(True)
        self.monitor_get_laser_enabled(sec)

        if disable:
            self.set_laser_enable(False)

    def monitor_get_laser_enabled(self, sec):
        now = datetime.now()
        end = now + timedelta(seconds=sec)
        print(f"\nmonitoring for {sec} seconds...")
        while now < end:
            enabled = self.get_laser_enabled()
            print(f"  {now}: laser_enable = {enabled}")
            sleep(0.5)
            now = datetime.now()

    def get_laser_enabled(self):
        return 0 != self.get_code(0xe2, label="GET_LASER_ENABLED", msb_len=1)

    def set_laser_watchdog(self, sec):
        print(f"Setting watchdog to {sec} seconds")
        return self.send_code(0xff, 0x18, sec, label="SET_LASER_WATCHDOG")

    def get_laser_watchdog(self):
        result = self.get_code(0xff, 0x17, label="GET_LASER_WATCHDOG")
        if result is None:
            print("GET_LASER_WATCHDOG returned NULL!")
            return -1

        msb = result[0] # big-endian
        lsb = result[1]
        sec = (msb << 8) | lsb

        print("get_laser_watchdog: %d sec (msb 0x%02x, lsb 0x%02x)" % (sec, msb, lsb))

        return sec

    def set_laser_enable(self, flag):
        print(f"{datetime.now()} setting laserEnable {flag}")
        self.send_code(0xbe, 1 if flag else 0)

    def get_firmware_version(self):
        result = self.get_code(0xc0)
        if result is not None and len(result) >= 4:
            return "%d.%d.%d.%d" % (result[3], result[2], result[1], result[0]) 

    def get_fpga_version(self):
        s = ""
        result = self.get_code(0xb4)
        if result is not None:
            for i in range(len(result)):
                c = result[i]
                if 0x20 <= c < 0x7f:
                    s += chr(c)
        return s

    def send_code(self, bRequest, wValue=0, wIndex=0, data_or_wLength=None, label=""):
        prefix = "" if not label else ("%s: " % label)
        result = None
        data_or_wLength = [0] * 8

        try:
            result = self.dev.ctrl_transfer(HOST_TO_DEVICE,
                                            bRequest,
                                            wValue,
                                            wIndex,
                                            data_or_wLength) 
        except Exception as exc:
            print("Hardware Failure FID Send Code Problem with ctrl transfer")
            return None

        print("%ssend_code: request 0x%02x value 0x%04x index 0x%04x data/len %s: result %s" % (
            prefix, bRequest, wValue, wIndex, data_or_wLength, result))
        return result

    def get_code(self, bRequest, wValue=0, wIndex=0, wLength=64, label="", msb_len=None, lsb_len=None):
        prefix = "" if not label else ("%s: " % label)
        result = None

        try:
            result = self.dev.ctrl_transfer(DEVICE_TO_HOST,
                                            bRequest,
                                            wValue,
                                            wIndex,
                                            wLength)
        except Exception as exc:
            print("Hardware Failure FID Get Code Problem with ctrl transfer")
            return None

        print("%sget_code: request 0x%02x value 0x%04x index 0x%04x = [%s]" % (
            prefix, bRequest, wValue, wIndex, result))

        if result is None:
            print("get_code[%s]: received null" % label)
            return None

        # demarshall or return raw array
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

################################################################################
# main()
################################################################################

fixture = TestFixture()
fixture.run()
